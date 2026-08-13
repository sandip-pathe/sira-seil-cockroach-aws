import assert from "node:assert/strict";
import test from "node:test";

import * as cdk from "aws-cdk-lib";
import { Match, Template } from "aws-cdk-lib/assertions";

import { SiraAwsStack, webBuildArgs } from "../lib/sira-aws-stack.js";

function template(): Template {
  const app = new cdk.App();
  const stack = new SiraAwsStack(app, "TestStack", {
    env: { account: "111111111111", region: "us-east-1" },
    stage: "test",
    chatModelId: "amazon.nova-micro-v1:0",
    embeddingModelId: "amazon.titan-embed-text-v2:0",
    workerOrganizationIds: "org_test",
    githubRepository: "sandip-pathe/sira-seil-cockroach-aws",
    githubBranch: "main",
    guardrailProfilePrefix: "us",
  });
  return Template.fromStack(stack);
}

test("synthesizes isolated durable application topology", () => {
  const rendered = template();

  rendered.resourceCountIs("AWS::ECS::Service", 4);
  rendered.resourceCountIs("AWS::ECS::TaskDefinition", 4);
  rendered.resourceCountIs("AWS::SQS::Queue", 4);
  rendered.resourceCountIs("AWS::S3::Bucket", 1);
  rendered.resourceCountIs("AWS::CloudFront::Distribution", 1);
  rendered.resourceCountIs("AWS::CloudFront::VpcOrigin", 1);
  rendered.resourceCountIs("AWS::Bedrock::Guardrail", 1);
  rendered.resourceCountIs("AWS::Bedrock::GuardrailVersion", 1);
  rendered.resourceCountIs("AWS::Bedrock::AutomatedReasoningPolicy", 1);
  rendered.resourceCountIs("AWS::Bedrock::AutomatedReasoningPolicyVersion", 1);
  rendered.resourceCountIs("AWS::BedrockAgentCore::Runtime", 1);
  rendered.resourceCountIs("AWS::BedrockAgentCore::RuntimeEndpoint", 1);
  rendered.resourceCountIs("AWS::Lambda::Function", 3);
  rendered.resourceCountIs("AWS::ApiGatewayV2::Api", 1);
  rendered.hasResourceProperties("AWS::ElasticLoadBalancingV2::LoadBalancer", {
    Scheme: "internal",
  });
  rendered.hasResourceProperties("AWS::CloudFront::Distribution", {
    DistributionConfig: Match.objectLike({
      Enabled: true,
      HttpVersion: "http2and3",
      DefaultCacheBehavior: Match.objectLike({ ViewerProtocolPolicy: "redirect-to-https" }),
    }),
  });
  rendered.hasResourceProperties("AWS::S3::Bucket", {
    VersioningConfiguration: { Status: "Enabled" },
    PublicAccessBlockConfiguration: {
      BlockPublicAcls: true,
      BlockPublicPolicy: true,
      IgnorePublicAcls: true,
      RestrictPublicBuckets: true,
    },
  });
  rendered.hasResourceProperties("AWS::SQS::Queue", {
    FifoQueue: true,
    VisibilityTimeout: 900,
    RedrivePolicy: Match.objectLike({ maxReceiveCount: 5 }),
  });
  rendered.hasOutput("QualificationDlqUrl", {});
  rendered.hasOutput("GithubDeployRoleArn", {});
  rendered.hasOutput("AgentCoreExperimentRuntimeArn", {});
  rendered.hasOutput("AutomatedReasoningPolicyVersionArn", {});
  rendered.hasOutput("ChangefeedWebhookUrl", {});
  rendered.hasOutput("ChangefeedWebhookTokenSecretName", {});
  rendered.hasOutput("ChangefeedHintQueueUrl", {});
  rendered.hasOutput("ChangefeedHintDlqUrl", {});
  rendered.hasResourceProperties("AWS::IAM::Role", {
    AssumeRolePolicyDocument: {
      Statement: Match.arrayWith([
        Match.objectLike({
          Action: "sts:AssumeRoleWithWebIdentity",
          Condition: {
            StringEquals: {
              "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
              "token.actions.githubusercontent.com:sub":
                "repo:sandip-pathe/sira-seil-cockroach-aws:ref:refs/heads/main",
            },
          },
        }),
      ]),
    },
  });
});

test("bridges authenticated at-least-once changefeed hints through a bounded Lambda", () => {
  const rendered = template();
  rendered.hasResourceProperties("AWS::Lambda::Function", {
    Architectures: ["arm64"],
    Handler: "sira_changefeed.handler.lambda_handler",
    ReservedConcurrentExecutions: 5,
    Runtime: "python3.13",
    Timeout: 10,
  });
  rendered.hasResourceProperties("AWS::ApiGatewayV2::Route", {
    RouteKey: "POST /cockroach/changefeed",
  });
  const serialized = JSON.stringify(rendered.toJSON());
  assert.match(serialized, /sqs:SendMessage/);
  assert.match(serialized, /secretsmanager:GetSecretValue/);
  assert.match(serialized, /changefeed-hint\.fifo/);
  assert.match(serialized, /changefeed-hint-dlq\.fifo/);
});

test("keeps Automated Reasoning explanatory and gives it an immutable policy version", () => {
  const rendered = template();

  rendered.hasResourceProperties("AWS::Bedrock::AutomatedReasoningPolicy", {
    PolicyDefinition: Match.objectLike({
      Version: "1.0",
      Rules: Match.arrayWith([
        Match.objectLike({
          Id: "SIRAAUTH0001",
          Expression: "(=> introductionReleased (and buyerConsented sellerConsented))",
        }),
        Match.objectLike({
          Id: "SIRAAUTH0003",
          Expression: "(=> purchaseExecuted humanApprovedPurchase)",
        }),
      ]),
    }),
  });
  rendered.hasResourceProperties("AWS::Bedrock::Guardrail", {
    AutomatedReasoningPolicyConfig: {
      ConfidenceThreshold: 0.8,
      Policies: Match.anyValue(),
    },
    CrossRegionConfig: {
      GuardrailProfileArn: Match.anyValue(),
    },
  });
  const serialized = JSON.stringify(rendered.toJSON());
  assert.match(serialized, /guardrail-profile\/us\.guardrail\.v1:0/);
  assert.match(serialized, /bedrock:InvokeAutomatedReasoningPolicy/);
});

test("runs a stateless bounded AgentCore evaluator without AgentCore Memory", () => {
  const rendered = template();

  rendered.hasResourceProperties("AWS::BedrockAgentCore::Runtime", {
    ProtocolConfiguration: "HTTP",
    NetworkConfiguration: { NetworkMode: "PUBLIC" },
    LifecycleConfiguration: {
      IdleRuntimeSessionTimeout: 300,
      MaxLifetime: 3600,
    },
  });
  rendered.resourceCountIs("AWS::BedrockAgentCore::Memory", 0);
  const serialized = JSON.stringify(rendered.toJSON());
  assert.match(serialized, /bedrock-agentcore:InvokeAgentRuntime/);
});

test("keeps tasks private and gives Bedrock only to the qualification role", () => {
  const rendered = template();

  const services = rendered.findResources("AWS::ECS::Service");
  assert.equal(Object.keys(services).length, 4);
  for (const service of Object.values(services)) {
    assert.equal(
      service.Properties.NetworkConfiguration.AwsvpcConfiguration.AssignPublicIp,
      "DISABLED",
    );
  }
  rendered.hasResourceProperties("AWS::IAM::Policy", {
    PolicyDocument: {
      Statement: Match.arrayWith([
        Match.objectLike({
          Action: Match.arrayWith(["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]),
          Effect: "Allow",
          Resource: Match.anyValue(),
        }),
      ]),
    },
  });
  const serialized = JSON.stringify(rendered.toJSON());
  assert.match(serialized, /foundation-model\/amazon\.nova-micro/);
  assert.match(serialized, /foundation-model\/amazon\.titan-embed-text/);
});

test("builds the web for the API-issued production guest-session mode", () => {
  assert.deepEqual(webBuildArgs, {
    NEXT_PUBLIC_WEB_DATA_MODE: "api",
    NEXT_PUBLIC_GUEST_SESSION_ENABLED: "true",
  });
});
