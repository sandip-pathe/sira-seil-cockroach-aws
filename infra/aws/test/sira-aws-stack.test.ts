import assert from "node:assert/strict";
import test from "node:test";

import * as cdk from "aws-cdk-lib";
import { Match, Template } from "aws-cdk-lib/assertions";

import { SiraAwsStack } from "../lib/sira-aws-stack.js";

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
  });
  return Template.fromStack(stack);
}

test("synthesizes isolated durable application topology", () => {
  const rendered = template();

  rendered.resourceCountIs("AWS::ECS::Service", 4);
  rendered.resourceCountIs("AWS::ECS::TaskDefinition", 4);
  rendered.resourceCountIs("AWS::SQS::Queue", 2);
  rendered.resourceCountIs("AWS::S3::Bucket", 1);
  rendered.resourceCountIs("AWS::CloudFront::Distribution", 1);
  rendered.resourceCountIs("AWS::CloudFront::VpcOrigin", 1);
  rendered.resourceCountIs("AWS::Bedrock::Guardrail", 1);
  rendered.resourceCountIs("AWS::Bedrock::GuardrailVersion", 1);
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
