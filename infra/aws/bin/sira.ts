#!/usr/bin/env node
import * as cdk from "aws-cdk-lib";

import { SiraAwsStack } from "../lib/sira-aws-stack.js";

const app = new cdk.App();
const stage = String(app.node.tryGetContext("stage") ?? "hackathon");

new SiraAwsStack(app, `Sira-${stage}`, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION ?? process.env.AWS_REGION ?? "us-east-1",
  },
  stage,
  chatModelId: String(app.node.tryGetContext("chatModelId") ?? "amazon.nova-micro-v1:0"),
  embeddingModelId: String(
    app.node.tryGetContext("embeddingModelId") ?? "amazon.titan-embed-text-v2:0",
  ),
  workerOrganizationIds: String(app.node.tryGetContext("workerOrganizationIds") ?? "org_consultco"),
  githubRepository: String(
    app.node.tryGetContext("githubRepository") ?? "sandip-pathe/sira-seil-cockroach-aws",
  ),
  githubBranch: String(app.node.tryGetContext("githubBranch") ?? "main"),
});
