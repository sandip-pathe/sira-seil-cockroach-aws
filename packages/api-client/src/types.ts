// Generated from contracts/openapi/openapi.json. Do not edit by hand.

export interface ApprovalCreate {
  actor_role: string;
  intent_hash: string;
}

export interface ApprovalRequestCreate {

}

export interface ApprovalRequestView {
  approved_roles: string[];
  expires_at: string;
  id: string;
  intent_hash: string;
  purchase_intent_id: string;
  required_roles: string[];
  status: ApprovalStatus;
}

export type ApprovalStatus = "NOT_REQUESTED" | "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED" | "SUPERSEDED";

export interface ApprovalView {
  approval_request_id?: string | null;
  intent_hash?: string | null;
  status: ApprovalStatus;
}

export interface CalibrationRunCreate {
  current_approach_id?: string;
  expected_qualifier_candidate_id?: string;
  known_failure_candidate_id?: string;
  proposed_changes?: { [key: string]: unknown; }[];
}

export interface CalibrationRunView {
  id: string;
  proposal?: { [key: string]: unknown; } | null;
  proposal_effective?: false;
  purchase_brief_version: number;
  purchase_request_id: string;
  results: { [key: string]: unknown; }[];
}

export type CandidateAction = "SHORTLIST" | "PASS" | "REQUEST_OFFER" | "SAVE_FOR_LATER" | "NOT_ENOUGH_EVIDENCE";

export interface CandidateActionCreate {
  action: CandidateAction;
  proposed_criterion_change?: { [key: string]: unknown; } | null;
  reason: string;
}

export interface CandidateActionView {
  action: CandidateAction;
  candidate_id: string;
  contact_details_revealed?: false;
  engagement_id?: string | null;
  id: string;
  proposal_effective?: false;
  proposal_id?: string | null;
  reason: string;
  request_id: string;
}

export type CandidateStatus = "ELIGIBLE" | "ELIGIBLE_WITH_EXCEPTION" | "CONDITIONAL" | "SIRA_INELIGIBLE" | "SEIL_PASS" | "UNAVAILABLE" | "STALE_EVIDENCE" | "INSUFFICIENT_EVIDENCE" | "CONFLICTING_EVIDENCE" | "AUTHORITY_REQUIRED";

export interface CandidateView {
  evidence?: string[];
  id: string;
  name: string;
  preference_score?: number | null;
  reason: string;
  reason_code?: string | null;
  seller_positioning?: string | null;
  stack_risk?: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL" | null;
  status: CandidateStatus;
  total_cost: MoneyView;
}

export interface CompanyContextView {
  facts_used: CompanyFactView[];
  hidden_fact_count: number;
  passport_version: number;
  stack_snapshot: number;
}

export interface CompanyFactView {
  display_name: string;
  display_value: string;
  fact_id: string;
  provenance_label: string;
  sensitivity: string;
}

export interface ConsentCreate {
  consent: boolean;
  scope?: "CONTACT_EXCHANGE";
}

export interface CounterfactualView {
  changed: boolean;
  company_aware_result_hash: string;
  company_aware_selected_candidate_id: string;
  decision_id: string;
  decisive_private_fact_ids: string[];
  explanation: string;
  generic_result_hash: string;
  generic_selected_candidate_id: string;
  remaining_uncertainties?: string[];
}

export interface CoverageView {
  evaluated_count: number;
  statement: string;
}

export interface DecisionLedgerView {
  buyer_passport_version: number;
  candidate_results: { [key: string]: unknown; }[];
  counterfactual: { [key: string]: unknown; };
  created_at: string;
  decision_hash: string;
  decision_id: string;
  evaluated_universe: { [key: string]: unknown; };
  policy_version: number;
  purchase_brief_id: string;
  purchase_brief_version: number;
  request_id: string;
  requirement_brief_id: string;
  requirement_brief_version: number;
  schema_version: string;
  selected_solution_plan_id: string;
  solution_plans: { [key: string]: unknown; }[];
  stack_snapshot: number;
}

export interface DecisionSimulationCreate {
  context_mode?: "COMPANY_AWARE" | "GENERIC_REQUEST_ONLY";
  preference_weight_overrides?: {  };
  reason: string;
}

export interface DecisionSimulationView {
  authoritative?: false;
  baseline_solution_plan_id: string;
  context_mode: "COMPANY_AWARE" | "GENERIC_REQUEST_ONLY";
  decision_id: string;
  input_hash: string;
  ranking_effect?: false;
  result_hash: string;
  simulated_order: string[];
  simulated_solution_plan_id: string;
  simulation_id: string;
}

export interface DecisionView {
  approval: ApprovalView;
  candidates: CandidateView[];
  company_context: CompanyContextView;
  counterfactual: { [key: string]: unknown; };
  coverage: CoverageView;
  fulfillment: FulfillmentView;
  payment: PaymentView;
  receipt?: { [key: string]: unknown; } | null;
  request: RequestDecisionHeader;
  selected_solution_plan: SolutionPlanView;
  stack_patch: StackPatchView;
}

export interface DesiredOutcomeInput {
  checkpoint_days: number;
  metric: string;
  target: number | number;
}

export type EngagementStatus = "NOT_STARTED" | "SELLER_REVIEWING" | "SELLER_PASSED" | "OFFER_AVAILABLE" | "BUYER_CONSENT_PENDING" | "SELLER_CONSENT_PENDING" | "INTRODUCTION_READY" | "DECLINED" | "EXPIRED";

export interface EngagementView {
  buyer_consented: boolean;
  contact_details?: { [key: string]: string; } | null;
  id: string;
  seller_consented: boolean;
  status: EngagementStatus;
}

export interface ErrorBody {
  code: string;
  details?: { [key: string]: unknown; };
  message: string;
  next_action?: string | null;
  request_id: string;
  retryable: boolean;
}

export interface ErrorEnvelope {
  error: ErrorBody;
}

export interface EvaluationReplayView {
  byte_stable: boolean;
  counterfactual_matches: boolean;
  decision_id: string;
  evaluation_run_id: string;
  ordering_matches: boolean;
  replayed_decision_hash: string;
  statuses_match: boolean;
  stored_decision_hash: string;
}

export type FulfillmentStatus = "NOT_STARTED" | "PENDING" | "PARTIAL" | "VERIFIED" | "FAILED_RETRYABLE" | "FAILED_FINAL" | "REVOKED";

export interface FulfillmentView {
  status: FulfillmentStatus;
  verified_entitlement_ids?: string[];
}

export interface HealthResponse {
  database: "configured" | "unavailable" | "not_checked";
  fixture_mode: boolean;
  service?: "sira-api";
  status: "ok" | "degraded";
  version: string;
}

export interface MoneyView {
  amount: string;
  currency: string;
}

export type PaymentStatus = "NOT_STARTED" | "SESSION_CREATED" | "CARDHOLDER_PENDING" | "CHECKOUT_PENDING" | "MERCHANT_APPROVED" | "REPORTING" | "PRAVA_COMPLETED" | "DECLINED" | "EXPIRED" | "UNCERTAIN" | "FAILED";

export interface PaymentView {
  provider_session_reference?: string | null;
  status: PaymentStatus;
}

export interface PravaSessionCreate {
  return_url: string;
}

export interface PravaSessionView {
  expires_at?: string | null;
  hosted_url?: string | null;
  id: string;
  missing_configuration?: string[];
  production_provider?: "PRAVA";
  production_verified?: false;
  purchase_intent_id: string;
  setup_blocked: boolean;
  status: PaymentStatus;
}

export interface ProposalDecisionCreate {
  reason: string;
}

export interface ProposalDecisionView {
  base_purchase_brief_id: string;
  proposal_id: string;
  ranking_effect: boolean;
  resulting_purchase_brief_id?: string | null;
  resulting_version?: number | null;
  status: "ACCEPTED" | "REJECTED";
}

export interface PurchaseBriefView {
  approval_requirements: { [key: string]: unknown; }[];
  calibration_examples: { [key: string]: unknown; }[];
  category_id: string;
  content_hash: string;
  created_at: string;
  desired_outcome: { [key: string]: unknown; };
  disclosure_choices: { [key: string]: unknown; };
  hard_gates: { [key: string]: unknown; }[];
  intent: string;
  known_alternatives: string[];
  organization_id: string;
  preferences: { [key: string]: unknown; }[];
  purchase_brief_id: string;
  request_id: string;
  schema_version: string;
  stackfile_impact_policy: { [key: string]: unknown; };
  stakeholder_roles: string[];
  status: string;
  supersedes_version?: number | null;
  version: number;
  visibility: RequestVisibility;
}

export interface PurchaseIntentCreate {
  solution_plan_id?: string | null;
}

export interface PurchaseIntentView {
  amount: string;
  approval_plan_hash: string;
  approval_policy_version: number;
  approval_requirement_set_id: string;
  approval_status: ApprovalStatus;
  approved_merchant_chain_id: string;
  billing_identity_id: string;
  buyer_legal_entity_id: string;
  contract_version_id: string;
  cost_center_id: string;
  currency: string;
  decision_hash: string;
  decision_id: string;
  expected_fulfillments: { [key: string]: unknown; }[];
  fee_amount: string;
  fulfillment_completion_policy: string;
  fulfillment_status: FulfillmentStatus;
  intent_hash: string;
  landed_total: string;
  line_items: { [key: string]: unknown; }[];
  locked_at: string;
  merchant: { [key: string]: string; };
  offer_id: string;
  offer_version: number;
  organization_id: string;
  pack_id: string;
  pack_version: number;
  payment_status: PaymentStatus;
  procurement_gate_result_hash: string;
  procurement_plan_id: string;
  purchase_intent_group_id?: string | null;
  purchase_intent_id: string;
  purchase_order_ref?: string | null;
  quote_expires_at: string;
  quote_id: string;
  quote_version: number;
  schema_version: string;
  seller_contracting_entity_id: string;
  solution_plan_id: string;
  tax_amount: string;
}

export interface PurchaseRequestCreate {
  deadline?: string | null;
  desired_outcome?: DesiredOutcomeInput | null;
  intent: string;
  jtbd_id?: string | null;
  stakeholders?: StakeholdersInput | null;
  visibility?: RequestVisibility;
}

export interface PurchaseRequestView {
  decision_id?: string | null;
  id: string;
  intent: string;
  organization_id: string;
  status: string;
  version: number;
  visibility: RequestVisibility;
  workflow_id?: string | null;
}

export interface PurchaseStatusView {
  approval_status: ApprovalStatus;
  deployment_state: "NOT_STARTED" | "STAGED" | "ACTIVE";
  fulfillment_status: FulfillmentStatus;
  outcome_state: "NOT_MEASURED" | "MEASURING" | "ACHIEVED" | "NOT_ACHIEVED";
  payment_status: PaymentStatus;
  purchase_intent_id: string;
  purchase_state: "AWAITING_APPROVAL" | "APPROVED_NOT_STARTED" | "PAYMENT_IN_PROGRESS" | "PAYMENT_NOT_COMPLETED" | "PAYMENT_UNCERTAIN" | "PAID_UNFULFILLED" | "PURCHASE_FULFILLED" | "REFUND_PENDING" | "REFUNDED";
}

export interface ReceiptView {
  amount: MoneyView;
  approval: { [key: string]: unknown; };
  decision_hash: string;
  decision_id: string;
  deployment_state: "NOT_STARTED" | "STAGED" | "ACTIVE";
  entitlements: { [key: string]: unknown; }[];
  fulfillment_status: FulfillmentStatus;
  intent_hash: string;
  merchant_order: { [key: string]: unknown; };
  offer: { [key: string]: unknown; };
  pack: { [key: string]: unknown; };
  payment_status: PaymentStatus;
  prava: { [key: string]: unknown; };
  purchase_intent_id: string;
  quote: { [key: string]: unknown; };
  receipt_hash: string;
  receipt_id: string;
  request_id: string;
}

export interface RequestDecisionHeader {
  id: string;
  intent: string;
  status: string;
}

export type RequestVisibility = "PRIVATE" | "SELECTIVE" | "OPEN_RFP";

export interface RequirementBriefView {
  allowed_stack_context: { [key: string]: unknown; };
  category_id: string;
  content_hash: string;
  data_profile: { [key: string]: unknown; };
  desired_outcome: string;
  expires_at: string;
  hard_requirements: { [key: string]: unknown; }[];
  intent: string;
  preferences: { [key: string]: unknown; }[];
  purchase_brief_id: string;
  purchase_brief_version: number;
  requirement_brief_id: string;
  schema_version: string;
  seller_questions: string[];
  team: { [key: string]: unknown; };
  version: number;
  visibility: RequestVisibility;
}

export interface SolutionPlanView {
  action: "REUSE_EXISTING" | "CONFIGURE_EXISTING" | "NO_ACTION" | "BUY" | "REPLACE" | "CONSOLIDATE";
  component_candidate_ids: string[];
  maximum_evidence_age_days: number;
  preference_score: number;
  rank: number;
  required_evidence_coverage_percent: number;
  solution_plan_id: string;
  stable_action_ids: string[];
  stack_patch_id: string;
  stack_risk: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  status: CandidateStatus;
  total_cost: MoneyView;
}

export interface StackfileView {
  current: { [key: string]: unknown; };
  organization_id: string;
  proposed_patch?: StackPatchView | null;
}

export interface StackPatchView {
  base_snapshot: number;
  content_hash: string;
  cost_impact: { [key: string]: unknown; };
  created_at: string;
  decision_id: string;
  expected_outcome: string;
  operations: { [key: string]: unknown; }[];
  organization_id: string;
  patch_id: string;
  prerequisites: string[];
  risk: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  rollback_plan: string[];
  schema_version: string;
  solution_plan_id: string;
  status: "PROPOSED" | "STAGED" | "APPROVED" | "APPLYING" | "APPLIED" | "REJECTED" | "CONFLICT" | "FAILED";
}

export interface StakeholdersInput {
  decision_maker_id: string;
  payer_id: string;
  user_group_ids?: string[];
}

export interface WorkflowAccepted {
  events_url: string;
  status_url: string;
  workflow_id: string;
}

export interface WorkflowView {
  aggregate_id: string;
  operation: string;
  result_reference?: string | null;
  safe_error_code?: string | null;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  workflow_id: string;
}

export interface Operations {
  accept_proposal: { method: "POST"; path: "/v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/accept"; pathParams: { brief_id: string; proposal_id: string; }; body: ProposalDecisionCreate; response: ProposalDecisionView; requiresIdempotency: true; };
  approve: { method: "POST"; path: "/v1/approval-requests/{approval_id}/approve"; pathParams: { approval_id: string; }; body: ApprovalCreate; response: ApprovalRequestView; requiresIdempotency: true; };
  candidate_action: { method: "POST"; path: "/v1/purchase-requests/{request_id}/candidates/{candidate_id}/actions"; pathParams: { request_id: string; candidate_id: string; }; body: CandidateActionCreate; response: CandidateActionView; requiresIdempotency: true; };
  create_approval_request: { method: "POST"; path: "/v1/purchase-intents/{intent_id}/approval-requests"; pathParams: { intent_id: string; }; body: ApprovalRequestCreate; response: ApprovalRequestView; requiresIdempotency: true; };
  create_prava_session: { method: "POST"; path: "/v1/purchase-intents/{intent_id}/prava-sessions"; pathParams: { intent_id: string; }; body: PravaSessionCreate; response: PravaSessionView; requiresIdempotency: true; };
  create_purchase_request: { method: "POST"; path: "/v1/purchase-requests"; pathParams: Record<never, never>; body: PurchaseRequestCreate; response: PurchaseRequestView; requiresIdempotency: true; };
  discover: { method: "POST"; path: "/v1/purchase-requests/{request_id}/discover"; pathParams: { request_id: string; }; body: never; response: WorkflowAccepted; requiresIdempotency: true; };
  get_counterfactuals: { method: "GET"; path: "/v1/decisions/{decision_id}/counterfactuals"; pathParams: { decision_id: string; }; body: never; response: CounterfactualView; requiresIdempotency: false; };
  get_decision: { method: "GET"; path: "/v1/decisions/{decision_id}"; pathParams: { decision_id: string; }; body: never; response: DecisionLedgerView; requiresIdempotency: false; };
  get_decision_view: { method: "GET"; path: "/v1/purchase-requests/{request_id}/decision-view"; pathParams: { request_id: string; }; body: never; response: DecisionView; requiresIdempotency: false; };
  get_purchase_brief: { method: "GET"; path: "/v1/purchase-requests/{request_id}/purchase-brief"; pathParams: { request_id: string; }; body: never; response: PurchaseBriefView; requiresIdempotency: false; };
  get_purchase_request: { method: "GET"; path: "/v1/purchase-requests/{request_id}"; pathParams: { request_id: string; }; body: never; response: PurchaseRequestView; requiresIdempotency: false; };
  get_receipt: { method: "GET"; path: "/v1/purchases/{purchase_id}/receipt"; pathParams: { purchase_id: string; }; body: never; response: ReceiptView; requiresIdempotency: false; };
  get_requirement_brief: { method: "GET"; path: "/v1/requirement-briefs/{brief_id}"; pathParams: { brief_id: string; }; body: never; response: RequirementBriefView; requiresIdempotency: false; };
  get_stackfile: { method: "GET"; path: "/v1/organizations/{organization_id}/stackfile"; pathParams: { organization_id: string; }; body: never; response: StackfileView; requiresIdempotency: false; };
  get_workflow: { method: "GET"; path: "/v1/workflows/{workflow_id}"; pathParams: { workflow_id: string; }; body: never; response: WorkflowView; requiresIdempotency: false; };
  get_workflow_events: { method: "GET"; path: "/v1/workflows/{workflow_id}/events"; pathParams: { workflow_id: string; }; body: never; response: ReadableStream<Uint8Array>; requiresIdempotency: false; };
  health: { method: "GET"; path: "/health"; pathParams: Record<never, never>; body: never; response: HealthResponse; requiresIdempotency: false; };
  lock_purchase_intent: { method: "POST"; path: "/v1/decisions/{decision_id}/purchase-intents"; pathParams: { decision_id: string; }; body: PurchaseIntentCreate; response: PurchaseIntentView; requiresIdempotency: true; };
  purchase_status: { method: "GET"; path: "/v1/purchase-intents/{intent_id}/status"; pathParams: { intent_id: string; }; body: never; response: PurchaseStatusView; requiresIdempotency: false; };
  record_consent: { method: "POST"; path: "/v1/engagements/{engagement_id}/consent"; pathParams: { engagement_id: string; }; body: ConsentCreate; response: EngagementView; requiresIdempotency: true; };
  reject_proposal: { method: "POST"; path: "/v1/purchase-briefs/{brief_id}/proposals/{proposal_id}/reject"; pathParams: { brief_id: string; proposal_id: string; }; body: ProposalDecisionCreate; response: ProposalDecisionView; requiresIdempotency: true; };
  replay_evaluation: { method: "POST"; path: "/v1/evaluation-runs/{evaluation_run_id}/replay"; pathParams: { evaluation_run_id: string; }; body: never; response: EvaluationReplayView; requiresIdempotency: false; };
  reset_demo: { method: "POST"; path: "/v1/demo/reset"; pathParams: Record<never, never>; body: never; response: { [key: string]: unknown; }; requiresIdempotency: false; };
  run_calibration: { method: "POST"; path: "/v1/purchase-requests/{request_id}/calibration-runs"; pathParams: { request_id: string; }; body: CalibrationRunCreate; response: CalibrationRunView; requiresIdempotency: true; };
  simulate_decision: { method: "POST"; path: "/v1/decisions/{decision_id}/simulations"; pathParams: { decision_id: string; }; body: DecisionSimulationCreate; response: DecisionSimulationView; requiresIdempotency: true; };
}

export type OperationId = keyof Operations;
