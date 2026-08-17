// Generated from contracts/openapi/openapi.json. Do not edit by hand.

export interface ActionDescriptor {
  expires_at?: string | null;
  href: string;
  id: string;
  label: string;
  method: "GET" | "POST" | "PATCH" | "DELETE";
  requires_confirmation: boolean;
}

export interface ActionRunCreate {
  decision_hash: string;
  decision_version: number;
  solution_plan_id: string;
}

export interface ActionRunView {
  action_run_id: string;
  action_type: "REUSE_EXISTING" | "CONFIGURE_EXISTING" | "NO_ACTION" | "BUY" | "RENEW" | "RESIZE" | "REPLACE" | "CANCEL";
  blocking_task?: BlockingTask | null;
  completed_at: string | null;
  created_at: string;
  current_step_id: string | null;
  decision_hash: string;
  decision_id: string;
  decision_version: number;
  execution_steps: ExecutionStep[];
  last_successful_checkpoint_id: string | null;
  owner_role: ActorRole;
  payment_handoff: PaymentHandoffProjection | null;
  recovery_action?: ActionDescriptor | null;
  result_artifacts: ResultArtifact[];
  schema_version: string;
  selection_id: string;
  solution_plan_id: string;
  status: OperationStatus;
  updated_at: string;
  workflow_id: string;
}

export interface ActiveOperation {
  current_checkpoint_id: string | null;
  id: string;
  kind: string;
  last_successful_checkpoint_id: string | null;
  owner_role: ActorRole;
  recovery_action?: ActionDescriptor | null;
  retryable: boolean;
  safe_to_leave: boolean;
  started_at: string;
  status: OperationStatus;
  updated_at: string;
}

export type ActorRole = "REQUESTER" | "DECISION_MAKER" | "POLICY_REVIEWER" | "BUDGET_OWNER" | "PROCUREMENT" | "IT_OPERATIONS" | "AUDITOR" | "SELLER_EDITOR" | "SELLER_REVIEWER" | "PLATFORM_OPERATOR";

export interface AgentProposalView {
  advisory_only?: boolean;
  payload: { [key: string]: unknown; };
  proposal_hash: string;
  proposal_type: string;
  ranking_effect?: boolean;
  requires_human_action?: boolean;
}

export interface ApprovalCreate {
  actor_role: string;
  intent_hash: string;
}

export interface ApprovalProjection {
  completed_count: number;
  expires_at?: string | null;
  href?: string | null;
  owner_roles: ActorRole[];
  rejected_by_role?: ActorRole | null;
  required: boolean;
  required_count: number;
  requirement_set_id?: string | null;
  status: ApprovalStatus;
}

export interface ApprovalRejectCreate {
  actor_role: string;
  intent_hash: string;
  reason: string;
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

export interface ApprovalRevokeCreate {
  actor_role: string;
  intent_hash: string;
  reason: string;
}

export type ApprovalStatus = "NOT_REQUIRED" | "NOT_REQUESTED" | "PENDING" | "APPROVED" | "REJECTED" | "REVOKED" | "EXPIRED" | "SUPERSEDED";

export interface AttentionView {
  kind: "question" | "approval" | "credential" | "choice" | "blocked";
  options?: string[];
  prompt: string;
  reason: string;
}

export interface BlockingTask {
  due_at: string | null;
  expires_at: string | null;
  href: string;
  id: string;
  owner_role: ActorRole;
  status: "OPEN" | "WAITING" | "BLOCKED" | "COMPLETED" | "EXPIRED";
  title: string;
}

export interface Body_seller_evidence_upload_evidence {
  claim_fields_json: string;
  evidence_file: string;
  observed_at?: string | null;
  source_class: string;
}

export interface BoundUnavailableView {
  reason_code: string;
  status?: "BOUND_UNAVAILABLE";
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

export interface CapabilityView {
  id: string;
  label: string;
  reason_code: string;
  remediation?: string | null;
  status: "disabled" | "misconfigured" | "ready" | "degraded" | "offline";
}

export interface CatalogProductView {
  billing_unit: string;
  claims: string[];
  edition: string;
  evidence_freshness?: string | null;
  evidence_status?: "PUBLISHED" | "RESEARCH_ONLY" | null;
  fit?: string | null;
  id: string;
  integrations: string[];
  listing_origin?: "SELLER_PUBLISHED" | "SEIL_RESEARCHED" | null;
  logo?: string | null;
  name: string;
  price: string;
  requirement_coverage?: string | null;
  seller: string;
  seller_attested?: boolean | null;
  source_refs?: { [key: string]: unknown; }[];
  status: string;
  summary: string;
  website?: string | null;
  why_company?: string | null;
}

export interface CompanyContextCreate {
  change_reason: string;
  kind: "REQUIREMENT" | "CONSTRAINT" | "STACK" | "POLICY" | "PREFERENCE" | "NOTE";
  label: string;
  payload: { [key: string]: unknown; };
}

export interface CompanyContextList {
  items: { [key: string]: unknown; }[];
}

export interface CompanyContextProjection {
  company_profile_version: number;
  company_stack_snapshot: number;
  facts_used: CompanyFactProjection[];
  hidden_fact_count: number;
}

export interface CompanyContextUpdate {
  change_reason: string;
  label: string;
  payload: { [key: string]: unknown; };
}

export interface CompanyContextView {
  item: { [key: string]: unknown; };
  versions: { [key: string]: unknown; }[];
}

export interface CompanyFactProjection {
  display_name: string;
  display_value: string;
  fact_id: string;
  provenance_label: string;
  sensitivity: "internal" | "confidential" | "restricted";
}

export type ComponentStatus = "ELIGIBLE" | "ELIGIBLE_WITH_EXCEPTION" | "CONDITIONAL" | "SIRA_INELIGIBLE" | "SEIL_PASS" | "UNAVAILABLE" | "STALE_EVIDENCE" | "INSUFFICIENT_EVIDENCE" | "CONFLICTING_EVIDENCE" | "AUTHORITY_REQUIRED" | "ADVISORY_ONLY";

export interface ConnectorView {
  id: string;
  meta: string;
  name: string;
  purpose: string;
  status: "Healthy" | "Needs setup" | "Not connected" | "Proof workspace";
}

export interface ConsentCreate {
  consent: boolean;
  scope?: "CONTACT_EXCHANGE";
}

export interface CostLineItemBoundsView {
  base: MoneyViewV2 | BoundUnavailableView;
  high: MoneyViewV2 | BoundUnavailableView;
  low: MoneyViewV2 | BoundUnavailableView;
  schedule_version: string | null;
  type: "MERCHANT_SUBTOTAL" | "SIRA_TRANSACTION_FEE" | "TAX" | "CONTRACT_COST" | "MIGRATION_COST" | "IMPLEMENTATION_COST";
}

export interface CounterfactualRecordView {
  after_evaluation_payload_hash: string | null;
  after_selected_plan_id: string | null;
  alternative_fact_id_sets: string[][];
  before_evaluation_payload_hash: string;
  before_selected_plan_id: string | null;
  changed_gate_ids: string[];
  generic_evaluation_payload_hash: string;
  generic_selected_plan_id: string | null;
  outcome: "WINNER_CHANGED" | "NO_SMALL_COUNTERFACTUAL_FOUND";
  record_hash: string;
  removed_fact_ids: string[];
  tested_limit: 3;
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

export interface CoverageBounds {
  conservative: ExactRatioView | BoundUnavailableView;
  optimistic: ExactRatioView | BoundUnavailableView;
}

export interface CoverageProjection {
  canonical_product_count: number;
  duplicate_count: number;
  evaluated_solution_plan_count: number;
  excluded_count: number;
  generated_solution_plan_count: number;
  product_evidence_option_count: number;
  raw_record_count: number;
  statement: string;
}

export interface DecisionComponentResult {
  component_id: string;
  current_instance_id: string | null;
  evidence_assessments: EvidenceAssessmentView[];
  gate_results: GateResultView[];
  name: string;
  pack_id: string | null;
  pack_version: number | null;
  primary_reason: GateReasonView | null;
  publisher_authority: PackAuthority | null;
  status: ComponentStatus;
}

export interface DecisionIndexView {
  active: DecisionRequestView[];
  available_actions: ActionDescriptor[];
  history: DecisionRequestView[];
}

export interface DecisionLedgerV2 {
  company_profile_version: number;
  component_results: DecisionComponentResult[];
  counterfactuals: CounterfactualRecordView[];
  created_at: string;
  decision_hash: string;
  decision_id: string;
  decision_outcome: DecisionOutcome;
  decision_state: DecisionVersionState;
  decision_version: number;
  evaluated_universe: EvaluatedUniverseView;
  evaluation: EvaluationRecord;
  policy_version: number;
  purchase_brief_id: string;
  purchase_brief_version: number;
  rank_stability: RankStabilityProjection;
  request_id: string;
  requirement_brief_id: string;
  requirement_brief_version: number;
  schema_version: string;
  selected_solution_plan_id: string | null;
  solution_plans: SolutionPlanRecord[];
  stack_snapshot: number;
  supersedes_decision_id: string | null;
}

export type DecisionOutcome = "SELECTED_SOLUTION_PLAN" | "NO_ELIGIBLE_SUPPORTED_ACTION";

export interface DecisionRequestCreate {
  deadline?: string | null;
  desired_outcome?: string | null;
  incumbent_instance_id?: string | null;
  intent: string;
  mission_id?: string | null;
  scenario_id?: string | null;
  visibility?: RequestVisibility;
}

export interface DecisionRequestHeader {
  decision_state: DecisionVersionState;
  decision_version: number;
  evaluation_mode: "DEVELOPMENT_FIXTURE_NON_PRODUCTION";
  fixture_label: "DEVELOPMENT_FIXTURE_NON_PRODUCTION";
  id: string;
  intent: string;
  scenario_id: string;
  status: "DRAFT" | "DISCOVERING" | "DECISION_READY" | "ACTION_IN_PROGRESS" | "RESULT_READY" | "COMPLETED";
  superseded_by?: string | null;
}

export interface DecisionRequestView {
  blocker?: string | null;
  current_decision_version?: number | null;
  current_stage: DecisionStage;
  deadline?: string | null;
  evaluation_mode: "SCENARIO_SELECTION_REQUIRED" | "DEVELOPMENT_FIXTURE_NON_PRODUCTION" | "PROVIDER_CONFIGURATION_REQUIRED";
  fixture_label?: "DEVELOPMENT_FIXTURE_NON_PRODUCTION" | null;
  href: string;
  id: string;
  intent: string;
  last_checkpoint: string;
  owner_role: ActorRole;
  scenario_id?: string | null;
  status: string;
  visibility: RequestVisibility;
}

export interface DecisionRuleItem {
  id: string;
  kind: "HARD_GATE" | "PREFERENCE" | "STACK_POLICY" | "APPROVAL";
  label: string;
  required: boolean;
  version: number;
  weight?: number | null;
}

export interface DecisionRulesView {
  content_hash: string;
  id: string;
  request_id: string;
  rules: DecisionRuleItem[];
  version: number;
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

export type DecisionStage = "NEED" | "COMPANY_FIT" | "OPTIONS" | "ACTION" | "RESULT";

export type DecisionVersionState = "CURRENT" | "SUPERSEDED";

export interface DecisionView {
  approval?: ApprovalProjection | null;
  company_context: CompanyContextProjection;
  coverage: CoverageProjection;
  decision_outcome: DecisionOutcome;
  disclosure_preview: DisclosurePreview;
  evaluation: EvaluationSummary;
  payment_handoff?: PaymentHandoffProjection | null;
  rank_stability: RankStabilityProjection;
  request: DecisionRequestHeader;
  result_artifacts: ResultArtifact[];
  selected_action_plan?: SelectedActionPlan | null;
  solution_options: SolutionOption[];
  stack_change?: StackChangeProjection | null;
  workflow: WorkflowProjection;
}

export interface DefaultComparison {
  cost: DefaultComparisonCost;
  next_action: string;
  stack_change: string;
}

export interface DefaultComparisonCost {
  amount: string;
  currency: "USD";
  horizon_days: number;
}

export interface DisclosureDefaults {
  allow_anonymized_requirement_preview?: boolean;
  allow_outcome_follow_up?: boolean;
  share_organization_name_after_consent?: boolean;
}

export interface DisclosurePreview {
  exact_fields: string[];
  expires_at: string;
  omitted_categories: string[];
  purpose: string;
  recipient: "SELLER";
  source_hash: string;
  source_id: string;
  source_version: number;
  status: "ACTIVE" | "EXPIRED";
  transformations: string[];
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

export interface EvaluatedUniverseView {
  canonical_product_count: number;
  coverage_statement: string;
  duplicate_count: number;
  evaluated_solution_plan_count: number;
  excluded_count: number;
  excluded_record_ids: string[];
  generated_solution_plan_count: number;
  identity_merges: IdentityMergeView[];
  included_record_ids: string[];
  product_evidence_option_count: number;
  raw_record_count: number;
}

export interface EvaluationRecord {
  bound_unavailable_plan_ids: string[];
  evaluated_at: string;
  evaluation_id: string;
  evaluation_payload_hash: string;
  frozen_versions: FrozenVersions;
  ordering_frontier_plan_ids: string[];
  ranked_solution_plan_ids: string[];
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

export interface EvaluationSummary {
  decision_hash: string;
  engine_version: string;
  id: string;
  payload_hash: string;
  pipeline_version: string;
}

export interface EvidenceAgeBounds {
  lower: ExactRatioView | BoundUnavailableView;
  upper: ExactRatioView | BoundUnavailableView;
}

export interface EvidenceAssessmentView {
  age_bounds: EvidenceAgeBounds | null;
  disputed: boolean;
  evidence_id: string;
  field: string;
  freshness_current: boolean | null;
  reasons: string[];
  reconstructable: boolean;
  record_id: string;
  revoked: boolean;
  scope_match: boolean;
  source_class: string;
  state: "ACCEPTABLE" | "UNKNOWN" | "STALE" | "CONFLICT";
  verification_method: string;
}

export interface EvidenceCoverageView {
  decision_material: CoverageBounds;
  hard: ExactRatioView;
}

export interface EvidenceFrontierItem {
  criterion_id: string;
  option_ids: string[];
  permitted_resolution?: string | null;
  reason_code: string;
}

export interface EvidenceSummary {
  href: string;
  id: string;
  label: string;
  publisher_authority: PackAuthority;
  verification_state: "VERIFIED" | "SELLER_ASSERTED" | "STALE" | "INSUFFICIENT" | "CONFLICTING" | "REVOKED";
}

export interface ExactRatioView {
  denominator: number;
  numerator: number;
}

export interface ExactScoreView {
  denominator: number;
  display: string;
  numerator: number;
}

export interface ExchangeCaseCreate {
  purchase_request_id: string;
  seller_organization_id: string;
}

export interface ExchangeCaseCreated {
  case_id: string;
  expires_at: string;
  projection: ExchangeProjectionView;
  route_capability: string;
}

export interface ExchangeEvidencePublish {
  evidence_hash: string;
  expected_version: number;
  published_span_ids: string[];
  summary: string;
}

export interface ExchangeOfferAccept {
  expected_version: number;
  offer_hash: string;
}

export interface ExchangeOfferApprove {
  approval_expires_at: string;
  expected_version: number;
  offer_hash: string;
}

export interface ExchangeOfferCreate {
  changed_terms?: string[];
  currency: string;
  expected_version: number;
  expires_at: string;
  lines: ExchangeOfferLineInput[];
  rationale: string;
  total: number | string;
}

export interface ExchangeOfferLineInput {
  description: string;
  item_id: string;
  quantity: number;
  unit_price: number | string;
}

export interface ExchangeProjectionView {
  case_id: string;
  party: "BUYER" | "SELLER";
  projection_hash: string;
  released: { [key: string]: unknown; };
  state: "CREATED" | "REQUIREMENT_RELEASED" | "EVIDENCE_RELEASED" | "OFFERED" | "COUNTERED" | "AGREED_PENDING_APPROVAL" | "APPROVED_FOR_HANDOFF" | "REJECTED" | "EXPIRED";
  version: number;
}

export interface ExecutionStep {
  artifact_id?: string | null;
  available_action?: ActionDescriptor | null;
  blocker?: string | null;
  checkpoint_id?: string | null;
  completed_at?: string | null;
  id: string;
  owner_role: ActorRole;
  started_at?: string | null;
  status: ExecutionStepStatus;
  type: ExecutionStepType;
}

export type ExecutionStepStatus = "NOT_REACHED" | "AVAILABLE" | "CURRENT" | "BLOCKED" | "COMPLETED" | "SKIPPED" | "FAILED_RETRYABLE" | "FAILED_FINAL";

export type ExecutionStepType = "REVIEW" | "REQUIRED_AUTHORITY" | "EXECUTE_OR_ASSIGN" | "VERIFY";

export interface FrozenVersions {
  company_profile: string;
  engine: string;
  fx: string;
  normalization: string;
  offer_set: string;
  pack_set: string;
  pipeline: string;
  policy: string;
  registry: string;
  request: string;
  stackfile: string;
  taxonomy: string;
}

export interface GateReasonView {
  detail: string;
  reason_code: string;
  status: ComponentStatus;
}

export interface GateResultView {
  evaluated_predicates: string[];
  gate_id: string;
  permitted_resolution: string | null;
  reasons: GateReasonView[];
  truth: TruthValue;
}

export interface HealthResponse {
  database: "configured" | "unavailable" | "not_checked";
  fixture_mode: boolean;
  service?: "sira-api";
  status: "ok" | "degraded";
  version: string;
}

export interface IdentityMergeView {
  canonical_id: string;
  merged_record_id: string;
  reasons: string[];
}

export interface MerchantProjection {
  id: string;
  offer_id: string;
}

export interface MissionArtifactView {
  authority: string;
  id: string;
  kind: string;
  payload: { [key: string]: unknown; };
  source_refs?: { [key: string]: unknown; }[];
  status?: string;
  title: string;
}

export interface MissionEventView {
  details?: { [key: string]: unknown; };
  id: string;
  occurred_at?: string | null;
  sequence: number;
  summary: string;
  type: string;
  verified?: boolean;
}

export interface MissionSnapshotView {
  artifacts: MissionArtifactView[];
  events: MissionEventView[];
  handoffs?: { [key: string]: unknown; }[];
  mission: MissionSummaryView;
  open_tasks?: { [key: string]: unknown; }[];
}

export interface MissionSummaryView {
  goal: string;
  id: string;
  mode: "sira" | "seil";
  plan?: { [key: string]: unknown; }[];
  state: string;
  stop_reason?: string | null;
  version: number;
}

export interface MoneyViewV2 {
  amount: string;
  currency: "USD";
}

export interface NotificationChannels {
  email?: boolean;
  in_app?: boolean;
}

export type OperationStatus = "QUEUED" | "RUNNING" | "WAITING_FOR_HUMAN" | "RETRYABLE_ERROR" | "UNCERTAIN" | "COMPLETED" | "FAILED_FINAL";

export type OptionFeedbackAction = "KEEP_FOR_COMPARISON" | "ELIMINATE" | "ASK_VENDOR" | "SAVE" | "NEED_EVIDENCE";

export interface OptionFeedbackCreate {
  action: OptionFeedbackAction;
  proposed_criterion_change?: {  } | null;
  reason: string;
}

export interface OptionFeedbackView {
  action: OptionFeedbackAction;
  contact_details_revealed?: false;
  engagement_id?: string | null;
  id: string;
  proposal_id?: string | null;
  ranking_effect?: false;
  reason: string;
  request_id: string;
  solution_plan_id: string;
}

export interface OutcomeCheckpointCreate {
  metric: string;
  observed_at: string;
  observed_value: string;
  source_class: "SYSTEM_OBSERVATION" | "HUMAN_ATTESTATION" | "PROVIDER_REPORT";
  source_reference: string;
}

export interface OutcomeCheckpointView {
  checkpoint_days: number;
  checkpoint_due_at: string;
  checkpoint_hash: string;
  decision_hash: string;
  decision_id: string;
  id: string;
  measurement_started_at: string;
  metric: string;
  observed_at: string;
  observed_value: string;
  preference_proposal?: { [key: string]: unknown; } | null;
  purchase_intent_id: string;
  solution_plan_id: string;
  source_class: "SYSTEM_OBSERVATION" | "HUMAN_ATTESTATION" | "PROVIDER_REPORT";
  source_reference_hash: string;
  state: "MEASURING" | "ACHIEVED" | "NOT_ACHIEVED" | "INCONCLUSIVE";
  target_operator: "gte" | "lte";
  target_value: string;
}

export type PackAuthority = "SELLER_SEALED" | "PLATFORM_COMPILED" | "EXTERNAL_UNSEALED";

export interface PaymentHandoffProjection {
  amount: string;
  approval_request_id: string;
  currency: string;
  destination_url: string;
  expires_at: string;
  handoff_hash: string;
  href: string;
  id: string;
  intent_hash: string;
  opened_at?: string | null;
  purchase_intent_id: string;
  recipient: string;
  reference: string;
  status: "READY" | "OPENED" | "EXPIRED" | "CANCELLED";
}

export interface PaymentHandoffView {
  amount: string;
  approval_request_id: string;
  currency: string;
  destination_url: string;
  expires_at: string;
  handoff_hash: string;
  id: string;
  intent_hash: string;
  opened_at?: string | null;
  purchase_intent_id: string;
  recipient: string;
  reference: string;
  status: "READY" | "OPENED" | "EXPIRED" | "CANCELLED";
}

export interface PlanComponentView {
  action_type: SolutionActionType;
  component_id: string;
  source_id: string;
  source_type: "PRODUCT_EVIDENCE" | "CURRENT_INSTANCE" | "CONTRACT" | "DEPENDENCY";
}

export interface PlanDimensionsView {
  bound_unavailable_reasons: string[];
  conflicting_count: number;
  cost_line_items: CostLineItemBoundsView[];
  decision_material_coverage: CoverageBounds;
  hard_coverage: ExactRatioView;
  maximum_evidence_age_ratio: EvidenceAgeBounds;
  payment_required: boolean;
  preference: PreferenceScoreBounds;
  stack_risk: StackRiskBounds;
  total_cost: TotalCostBounds;
  universe_coverage: ExactRatioView;
  unresolved_count: number;
}

export interface PlanSelectionCreate {
  decision_hash: string;
  decision_version: number;
  solution_plan_id: string;
}

export type PlanSelectionState = "SELECTED" | "SUPERSEDED" | "CANCELLED";

export interface PlanSelectionView {
  action_run_href?: string | null;
  decision_hash: string;
  decision_version: number;
  selected_decision_id: string;
  selection_id: string;
  solution_plan_id: string;
  source_decision_id: string;
  state: PlanSelectionState;
}

export interface PreferenceScoreBounds {
  conservative: ExactScoreView;
  optimistic: ExactScoreView;
}

export interface ProductEvidenceComponent {
  action: "ADD" | "REMOVE" | "RETAIN" | "CONFIGURE" | "RENEW" | "RESIZE" | "CANCEL" | "REUSE";
  current_instance_id: string | null;
  product_evidence_id: string | null;
  publisher_authority: PackAuthority | null;
  verification_summary: string;
}

export interface ProposalDecisionCreate {
  reason: string;
}

export interface ProposalDecisionView {
  base_purchase_brief_id: string;
  proposal_id: string;
  ranking_effect: boolean;
  resulting_decision_hash?: string | null;
  resulting_decision_id?: string | null;
  resulting_decision_version?: number | null;
  resulting_purchase_brief_id?: string | null;
  resulting_version?: number | null;
  status: "ACCEPTED" | "REJECTED";
}

export interface PublicMarketplaceProductView {
  product: { [key: string]: unknown; };
}

export interface PublicMarketplaceSearchView {
  category: string;
  query_model_id: string;
  results: { [key: string]: unknown; }[];
}

export interface PublisherAuthorityProjection {
  label: string;
  supporting_copy: string;
  value: PackAuthority;
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
  decision_version: number;
  expected_fulfillments: { [key: string]: unknown; }[];
  fee_amount: string;
  fee_schedule_version: string;
  fulfillment_completion_policy: string;
  intent_hash: string;
  landed_total: string;
  line_items: { [key: string]: unknown; }[];
  locked_at: string;
  merchant: { [key: string]: string; };
  merchant_subtotal: string;
  offer_id: string;
  offer_version: number;
  organization_id: string;
  pack_id: string;
  pack_version: number;
  procurement_gate_result_hash: string;
  procurement_plan_id: string;
  purchase_intent_group_id?: string | null;
  purchase_intent_id: string;
  purchase_order_ref?: string | null;
  quote_expires_at: string;
  quote_id: string;
  quote_version: number;
  schema_version: string;
  selection_id: string;
  seller_contracting_entity_id: string;
  solution_plan_id: string;
  stack_patch_id: string;
  tax_amount: string;
}

export interface PurchaseStatusView {
  approval_status: ApprovalStatus;
  handoff_status: "READY" | "OPENED" | "EXPIRED" | "CANCELLED" | null;
  outcome_state: "NOT_MEASURED" | "MEASURING" | "ACHIEVED" | "NOT_ACHIEVED" | "INCONCLUSIVE";
  purchase_intent_id: string;
  purchase_state: "AWAITING_APPROVAL" | "READY_FOR_HANDOFF" | "HANDOFF_OPENED" | "HANDOFF_EXPIRED" | "HANDOFF_CANCELLED";
}

export interface QualificationApprovalCreate {
  action: "APPROVE" | "REJECT";
  reason: string;
}

export interface QualificationConsentCreate {
  shared_fields: { [key: string]: unknown; };
}

export interface QualificationEngagementView {
  consents: { [key: string]: unknown; }[];
  engagement: { [key: string]: unknown; };
  introduction: { [key: string]: unknown; } | null;
  seller_response: { [key: string]: unknown; } | null;
}

export interface QualificationEventFeed {
  events: { [key: string]: unknown; }[];
  next_cursor: string | null;
}

export interface QualificationInboxView {
  items: { [key: string]: unknown; }[];
  next_cursor?: string | null;
  workspace: "BUYER" | "SELLER";
}

export interface QualificationIntegrityView {
  checked_at: string;
  checks: { [key: string]: unknown; }[];
  mission_id: string;
  verdict: "PASS" | "FAIL" | "PENDING";
}

export interface QualificationIntroductionCreate {
  shared_fields: { [key: string]: unknown; };
}

export interface QualificationMissionCreate {
  buyer_context: { [key: string]: unknown; };
  company_context_item_ids?: string[];
  procurement_policy: { [key: string]: unknown; };
  requirement_brief: RequirementBriefCreate;
}

export interface QualificationMissionView {
  attempts: { [key: string]: unknown; }[];
  decision: { [key: string]: unknown; } | null;
  engagement: { [key: string]: unknown; } | null;
  integrity: { [key: string]: unknown; };
  mission: { [key: string]: unknown; };
}

export interface QualificationMutationView {
  input_digest?: string | null;
  replayed?: boolean;
  resource_id: string;
  resource_type: string;
  state: string;
}

export interface QualificationSellerResponseCreate {
  cited_evidence_ids?: string[];
  message?: string | null;
  response: "FIT" | "ANTI_FIT" | "NEEDS_INFO";
}

export interface QuietHours {
  enabled?: boolean;
  end?: string;
  start?: string;
  timezone?: string;
}

export type RankStability = "STABLE" | "UNSTABLE" | "UNDETERMINED";

export interface RankStabilityProjection {
  evidence_frontier: EvidenceFrontierItem[];
  status: RankStability;
  summary: string;
}

export type RequestVisibility = "PRIVATE" | "SELECTIVE" | "OPEN_RFP";

export interface RequirementBriefCreate {
  category: string;
  criteria: RequirementCriterion[];
  goal: string;
  seller_visible_requirements?: { [key: string]: unknown; };
}

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

export interface RequirementCriterion {
  id: string;
  label: string;
  priority?: "MUST" | "SHOULD" | "COULD";
  requirement: string;
}

export interface ResultArtifact {
  actor_ref: string | null;
  href: string;
  id: string;
  occurred_at: string;
  owner_role: ActorRole;
  safe_label: string;
  stack_patch_id: string | null;
  type: ResultArtifactType;
  verification_state: "PENDING" | "VERIFIED" | "FAILED" | "REVOKED";
  verified_at?: string | null;
}

export type ResultArtifactType = "DECISION_RECORD" | "CONFIGURATION_CHANGE" | "CONTRACT_CONFIRMATION" | "CANCELLATION_CONFIRMATION" | "MIGRATION_RECORD" | "STACK_PATCH" | "OUTCOME_CHECKPOINT";

export interface ScoreComponentView {
  conservative_contribution: ExactRatioView;
  conservative_satisfaction: ExactRatioView;
  coverage_weight: number;
  criterion_id: string;
  evidence_ids: string[];
  evidence_state: "ACCEPTABLE" | "UNKNOWN" | "STALE" | "CONFLICT";
  optimistic_contribution: ExactRatioView;
  optimistic_satisfaction: ExactRatioView;
  prior_label: string | null;
  weight: number;
}

export interface SelectedActionPlan {
  action_type: "REUSE_EXISTING" | "CONFIGURE_EXISTING" | "NO_ACTION" | "BUY" | "RENEW" | "RESIZE" | "REPLACE" | "CANCEL";
  decision_hash: string;
  decision_version: number;
  execution_steps: ExecutionStep[];
  href: string;
  id: string;
  selected_at: string;
  selected_by_role: ActorRole;
  selection_id: string;
  state: PlanSelectionState;
}

export interface SellerActionDescriptor {
  href: string;
  id: string;
  label: string;
  method: "GET" | "POST" | "PATCH";
  requires_confirmation: boolean;
}

export interface SellerActivityMetrics {
  answer_rendered_count: number;
  href: string;
  measurement_label?: "OBSERVATIONAL_NOT_CAUSAL";
  observed_self_service_count: number;
  seller_handoff_requested_count: number;
  window_end: string;
  window_start: string;
}

export interface SellerActor {
  capabilities: SellerCapability[];
  role: "SELLER_EDITOR" | "SELLER_REVIEWER" | "PLATFORM_OPERATOR";
}

export type SellerCapability = "CLAIM_PRODUCT" | "VIEW_OWN_DRAFT" | "EDIT_CLAIMS" | "ADD_EVIDENCE" | "SUBMIT_REVIEW" | "REQUEST_CHANGES" | "APPROVE_REVIEW" | "REJECT_REVIEW" | "PUBLISH" | "SUSPEND" | "EXPORT" | "VIEW_ACTIVITY_METRICS" | "RETRY_PUBLICATION";

export interface SellerClaimCreate {
  authority_proof_reference: string;
  requested_role?: ActorRole;
}

export interface SellerClaimView {
  claim_id: string;
  product_id: string;
  safe_reason?: string | null;
  state: SellerEvidenceState;
  submitted_at: string;
}

export interface SellerEvidenceAttachCreate {
  claim_fields: string[];
  observed_at?: string | null;
  source_class: string;
  source_reference: string;
}

export interface SellerEvidenceAttachmentView {
  content_type?: string | null;
  draft_id: string;
  id: string;
  object_checksum?: string | null;
  size_bytes?: number | null;
  source_reference_hash: string;
  verification_state: "UNVERIFIED" | "PENDING" | "VERIFIED" | "REJECTED";
  version_bound?: boolean;
}

export interface SellerEvidenceClaim {
  evidence_ids: string[];
  field: string;
  value: string | number | boolean | string[] | null;
}

export interface SellerEvidenceProduct {
  current_version: number;
  href: string;
  id: string;
  name: string;
  seller_state: SellerEvidenceState;
}

export type SellerEvidenceState = "UNCLAIMED" | "CLAIM_PENDING" | "CLAIM_DENIED" | "SELLER_DRAFT" | "VALIDATION_CONFLICT" | "IN_REVIEW" | "CHANGES_REQUESTED" | "PUBLISH_READY" | "PUBLISHED" | "SUPERSEDED" | "PUBLICATION_FAILED";

export interface SellerEvidenceView {
  activity_metrics: SellerActivityMetrics;
  actor: SellerActor;
  available_actions: SellerActionDescriptor[];
  pack_health: SellerPackHealth;
  product: SellerEvidenceProduct;
  publisher_authority: PublisherAuthorityProjection;
  reusable_answers: SellerReusableAnswers;
  review?: SellerReviewSummary | null;
  validation: SellerValidation;
  version_links: SellerVersionLinks;
}

export type SellerExportFormat = "JSON" | "HTML" | "REUSABLE_ANSWER";

export interface SellerPackDraftPatch {
  anti_fit_rules?: SellerEvidenceClaim[];
  base_revision: number;
  claims?: SellerEvidenceClaim[];
  fit_rules?: SellerEvidenceClaim[];
  proof_adapter?: SellerProofAdapterDraft | null;
}

export interface SellerPackDraftView {
  anti_fit_rules: SellerEvidenceClaim[];
  claims: SellerEvidenceClaim[];
  fit_rules: SellerEvidenceClaim[];
  id: string;
  product_id: string;
  proof_adapter?: SellerProofAdapterDraft | null;
  publisher_authority: PackAuthority;
  revision: number;
  revision_hash: string;
  state: SellerEvidenceState;
  updated_at: string;
  validation: SellerValidation;
}

export interface SellerPackExport {
  content_hash: string;
  format: SellerExportFormat;
  generated_at: string;
  href: string;
  pack_id: string;
  pack_version: number;
  publisher_authority: PackAuthority;
  verification_summary: string;
}

export interface SellerPackExportsView {
  exports: SellerPackExport[];
}

export interface SellerPackHealth {
  complete_claim_count: number;
  conflict_count: number;
  required_claim_count: number;
  stale_claim_count: number;
  status: "HEALTHY" | "NEEDS_ATTENTION" | "BLOCKED";
}

export interface SellerPackVersionView {
  content_hash: string;
  id: string;
  product_id: string;
  proof_adapter?: SellerProofAdapterDraft | null;
  published_at?: string | null;
  publisher_authority: PackAuthority;
  state: SellerEvidenceState;
  version: number;
}

export interface SellerProductSearchItem {
  category: string;
  href: string;
  id: string;
  name: string;
  public_summary: string;
  publisher_authority: PackAuthority;
  state: SellerEvidenceState;
}

export interface SellerProductSearchView {
  results: SellerProductSearchItem[];
}

export interface SellerProofAdapterDraft {
  adapter_id: string;
  artifact_digest: string;
  capabilities: Array<"SUPPORT_SUMMARIZATION" | "CUSTOMER_EMAIL_OUTPUT" | "PII_REDACTION">;
  conformance_hash: string;
  declared_region: "EU" | "IN" | "US";
  fixed_price: SellerProofAdapterPrice;
  protocol_version: "TrialCase/v0";
}

export interface SellerProofAdapterPrice {
  amount: string;
  currency?: "USD";
}

export interface SellerPublishCreate {
  revision_hash: string;
}

export interface SellerReusableAnswers {
  formats: SellerExportFormat[];
  href?: string | null;
  published_answer_count: number;
  published_version?: number | null;
}

export type SellerReviewDecision = "REQUEST_CHANGES" | "APPROVE" | "REJECT";

export interface SellerReviewDecisionCreate {
  decision: SellerReviewDecision;
  reason: string;
  revision_hash: string;
}

export interface SellerReviewDecisionView {
  actor_role: ActorRole;
  decision: SellerReviewDecision;
  draft_id: string;
  id: string;
  occurred_at: string;
  reason: string;
  revision_hash: string;
}

export interface SellerReviewSummary {
  decision: SellerReviewDecision | null;
  reason?: string | null;
  recorded_at: string | null;
  review_id: string;
  reviewer_role: "SELLER_REVIEWER" | "PLATFORM_OPERATOR";
  revision_hash: string;
  status: "PENDING" | "COMPLETED";
}

export interface SellerSubmitReviewCreate {
  revision_hash: string;
}

export interface SellerSuspendCreate {
  effective_at: string;
  reason: string;
}

export interface SellerValidation {
  gaps: SellerValidationGap[];
  status: "NOT_RUN" | "VALID" | "HAS_GAPS" | "CONFLICT";
}

export interface SellerValidationGap {
  field: string;
  href: string;
  id: string;
  safe_message: string;
}

export interface SellerVersionLinks {
  current: string;
  previous?: string | null;
}

export type SolutionActionType = "REUSE_EXISTING" | "CONFIGURE_EXISTING" | "NO_ACTION" | "BUY" | "RENEW" | "RESIZE" | "REPLACE" | "CONSOLIDATE" | "CANCEL";

export interface SolutionOption {
  action_type: SolutionActionType;
  components: ProductEvidenceComponent[];
  default_comparison: DefaultComparison;
  evidence: EvidenceSummary[];
  evidence_coverage: EvidenceCoverageView;
  evidence_frontier: EvidenceFrontierItem[];
  id: string;
  label: string;
  maximum_evidence_age_ratio: EvidenceAgeBounds;
  merchant?: MerchantProjection | null;
  ordering_frontier_member: boolean;
  permitted_resolution?: string | null;
  preference_score: PreferenceScoreBounds;
  quote_policy_reason: string;
  quote_required: boolean;
  reason: string;
  reason_code?: string | null;
  resolution_frontier_member: boolean;
  seller_positioning?: string | null;
  stack_risk: StackRiskBounds;
  status: SolutionOptionStatus;
  total_cost: TotalCostBounds;
}

export type SolutionOptionStatus = "SUPPORTED" | "SUPPORTED_WITH_EXCEPTION" | "NEEDS_CONDITION" | "BLOCKED_BY_COMPANY_REQUIREMENT" | "VENDOR_NOT_SUPPORTED" | "UNAVAILABLE" | "NEEDS_EVIDENCE" | "EVIDENCE_CONFLICT" | "AUTHORITY_REQUIRED" | "RESEARCH_ONLY";

export type SolutionPlanLifecycle = "CANDIDATE" | "RESOLUTION_PENDING" | "EXECUTABLE" | "BLOCKED";

export interface SolutionPlanRecord {
  action_type: SolutionActionType;
  autonomous_execution_allowed: boolean;
  component_hash: string;
  components: PlanComponentView[];
  construction_lifecycle: "CANDIDATE";
  dimensions: PlanDimensionsView;
  gate_results: GateResultView[];
  lifecycle: SolutionPlanLifecycle;
  ordering_frontier_member: boolean;
  permitted_resolution: string | null;
  primary_reason: GateReasonView | null;
  quote_policy_reason: string;
  quote_required: boolean;
  rank: number | null;
  resolution_frontier_member: boolean;
  score_components: ScoreComponentView[];
  solution_plan_id: string;
  stable_action_ids: string[];
  stack_patch_id: string | null;
  status: ComponentStatus;
}

export interface StackChangeProjection {
  added: string[];
  dependency_changed: string[];
  href: string;
  id: string;
  removed: string[];
  retained: string[];
  staged_for_removal: string[];
  status: "PROPOSED" | "STAGED" | "APPLIED" | "REJECTED" | "SUPERSEDED";
  summary: string;
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

export type StackRisk = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export interface StackRiskBounds {
  base: StackRisk | BoundUnavailableView;
  lower: StackRisk | BoundUnavailableView;
  upper: StackRisk | BoundUnavailableView;
}

export interface StageHistoryEntry {
  checkpoint_id: string | null;
  completed_at?: string | null;
  href: string;
  stage: DecisionStage;
  status: StageStatus;
}

export type StageStatus = "NOT_STARTED" | "READY" | "CURRENT" | "WAITING" | "BLOCKED" | "COMPLETED" | "SUPERSEDED";

export interface TotalCostBounds {
  base: MoneyViewV2 | BoundUnavailableView;
  high: MoneyViewV2 | BoundUnavailableView;
  low: MoneyViewV2 | BoundUnavailableView;
}

export type TruthValue = "TRUE" | "FALSE" | "UNKNOWN" | "CONFLICT" | "UNRESOLVED";

export type UIActionCapability = "VIEW_DECISION" | "EDIT_REQUEST" | "ANSWER_TASK" | "VIEW_PRIVATE_COMPANY_FACTS" | "KEEP_OPTION" | "ELIMINATE_OPTION" | "ASK_VENDOR" | "SAVE_OPTION" | "REQUEST_EVIDENCE" | "SELECT_PLAN" | "ACCEPT_EXCEPTION" | "APPROVE_POLICY" | "APPROVE_BUDGET" | "OPEN_PAYMENT_HANDOFF" | "EXECUTE_CONFIGURATION" | "PROVIDE_OUTCOME" | "EXPORT_AUDIT" | "EDIT_PRODUCT_EVIDENCE" | "REVIEW_PRODUCT_EVIDENCE" | "PUBLISH_PRODUCT_EVIDENCE" | "SUSPEND_PRODUCT_EVIDENCE";

export interface VersionLinks {
  current: string;
  previous?: string | null;
  superseded_by?: string | null;
}

export interface WorkflowAccepted {
  events_url: string;
  status_url: string;
  workflow_id: string;
}

export interface WorkflowActor {
  capabilities: UIActionCapability[];
  role: ActorRole;
}

export interface WorkflowProjection {
  active_operation?: ActiveOperation | null;
  actor: WorkflowActor;
  available_actions: ActionDescriptor[];
  blocking_tasks: BlockingTask[];
  current_stage: DecisionStage;
  stage_history: StageHistoryEntry[];
  version_links: VersionLinks;
}

export interface WorkflowView {
  aggregate_id: string;
  operation: string;
  result_reference?: string | null;
  safe_error_code?: string | null;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  workflow_id: string;
}

export interface WorkspaceAnalyticsView {
  current_state: { [key: string]: number; };
  daily_events: { [key: string]: unknown; }[];
  funnel: { [key: string]: number; };
  generated_at: string;
  measurement_label: "OBSERVATIONAL_NOT_CAUSAL";
  window_days: number;
  workspace: "BUYER" | "SELLER";
}

export interface WorkspaceChatCreate {
  conversation_id?: string | null;
  history?: WorkspaceMessage[];
  message: string;
  mission_id?: string | null;
  mode?: "sira" | "seil";
}

export interface WorkspaceChatView {
  advisory_only?: boolean;
  artifacts?: MissionArtifactView[];
  attention?: AttentionView | null;
  conversation_id: string;
  events?: MissionEventView[];
  follow_up_required?: boolean;
  message: string;
  mission: MissionSummaryView;
  mission_id: string;
  panel?: "catalog" | "connectors" | "decisions" | "inbox" | null;
  products?: CatalogProductView[];
  proposals?: AgentProposalView[];
  tool_calls?: string[];
}

export interface WorkspaceConversationView {
  artifacts?: MissionArtifactView[];
  events?: MissionEventView[];
  id: string;
  messages: WorkspaceMessage[];
  mission: MissionSummaryView;
  mode: "sira" | "seil";
  open_tasks?: { [key: string]: unknown; }[];
  title: string;
  updated_at: string;
}

export interface WorkspaceMessage {
  content: string;
  proposals?: AgentProposalView[];
  role: "user" | "assistant";
  tool_calls?: string[];
}

export interface WorkspaceSettingsUpdate {
  change_reason: string;
  disclosure_defaults: DisclosureDefaults;
  notification_channels: NotificationChannels;
  quiet_hours: QuietHours;
}

export interface WorkspaceSettingsView {
  consent_boundary: "BILATERAL_EXACT_FIELD_MATCH_REQUIRED";
  current_hash: string;
  current_version: number;
  disclosure_defaults: DisclosureDefaults;
  etag: string;
  id: string | null;
  notification_channels: NotificationChannels;
  party: "BUYER" | "SELLER";
  persisted: boolean;
  quiet_hours: QuietHours;
  updated_at: string | null;
}

export interface Operations {
  accept_exchange_offer: { method: "POST"; path: "/v1/exchange-cases/{case_id}/accept"; pathParams: { case_id: string; }; queryParams: { route: string; }; body: ExchangeOfferAccept; response: ExchangeProjectionView; requiresIdempotency: true; };
  accept_rule_proposal: { method: "POST"; path: "/v1/decision-rules/{rules_id}/proposals/{proposal_id}/accept"; pathParams: { rules_id: string; proposal_id: string; }; queryParams: Record<never, never>; body: ProposalDecisionCreate; response: ProposalDecisionView; requiresIdempotency: true; };
  approve: { method: "POST"; path: "/v1/approval-requests/{approval_id}/approve"; pathParams: { approval_id: string; }; queryParams: Record<never, never>; body: ApprovalCreate; response: ApprovalRequestView; requiresIdempotency: true; };
  approve_exchange_offer: { method: "POST"; path: "/v1/exchange-cases/{case_id}/approve"; pathParams: { case_id: string; }; queryParams: { route: string; }; body: ExchangeOfferApprove; response: ExchangeProjectionView; requiresIdempotency: true; };
  create_approval_request: { method: "POST"; path: "/v1/purchase-intents/{intent_id}/approval-requests"; pathParams: { intent_id: string; }; queryParams: Record<never, never>; body: ApprovalRequestCreate; response: ApprovalRequestView; requiresIdempotency: true; };
  create_decision_request: { method: "POST"; path: "/v1/decision-requests"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: DecisionRequestCreate; response: DecisionRequestView; requiresIdempotency: true; };
  create_exchange_case: { method: "POST"; path: "/v1/exchange-cases"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: ExchangeCaseCreate; response: ExchangeCaseCreated; requiresIdempotency: true; };
  create_payment_handoff: { method: "POST"; path: "/v1/purchase-intents/{intent_id}/payment-handoff"; pathParams: { intent_id: string; }; queryParams: Record<never, never>; body: never; response: PaymentHandoffView; requiresIdempotency: true; };
  discover_decision_request: { method: "POST"; path: "/v1/decision-requests/{request_id}/discover"; pathParams: { request_id: string; }; queryParams: Record<never, never>; body: never; response: WorkflowAccepted; requiresIdempotency: true; };
  get_action_run: { method: "GET"; path: "/v1/action-runs/{action_run_id}"; pathParams: { action_run_id: string; }; queryParams: Record<never, never>; body: never; response: ActionRunView; requiresIdempotency: false; };
  get_counterfactuals: { method: "GET"; path: "/v1/decisions/{decision_id}/counterfactuals"; pathParams: { decision_id: string; }; queryParams: Record<never, never>; body: never; response: CounterfactualView; requiresIdempotency: false; };
  get_decision_ledger_v2: { method: "GET"; path: "/v1/decisions/{decision_id}"; pathParams: { decision_id: string; }; queryParams: Record<never, never>; body: never; response: DecisionLedgerV2; requiresIdempotency: false; };
  get_decision_request: { method: "GET"; path: "/v1/decision-requests/{request_id}"; pathParams: { request_id: string; }; queryParams: Record<never, never>; body: never; response: DecisionRequestView; requiresIdempotency: false; };
  get_decision_room: { method: "GET"; path: "/v1/decision-requests/{request_id}/decision-view"; pathParams: { request_id: string; }; queryParams: { version?: number | null; }; body: never; response: DecisionView; requiresIdempotency: false; };
  get_decision_rules: { method: "GET"; path: "/v1/decision-requests/{request_id}/decision-rules"; pathParams: { request_id: string; }; queryParams: Record<never, never>; body: never; response: DecisionRulesView; requiresIdempotency: false; };
  get_exchange_case: { method: "GET"; path: "/v1/exchange-cases/{case_id}"; pathParams: { case_id: string; }; queryParams: { route: string; }; body: never; response: ExchangeProjectionView; requiresIdempotency: false; };
  get_requirement_brief: { method: "GET"; path: "/v1/requirement-briefs/{brief_id}"; pathParams: { brief_id: string; }; queryParams: Record<never, never>; body: never; response: RequirementBriefView; requiresIdempotency: false; };
  get_stackfile: { method: "GET"; path: "/v1/organizations/{organization_id}/stackfile"; pathParams: { organization_id: string; }; queryParams: Record<never, never>; body: never; response: StackfileView; requiresIdempotency: false; };
  get_workflow: { method: "GET"; path: "/v1/workflows/{workflow_id}"; pathParams: { workflow_id: string; }; queryParams: Record<never, never>; body: never; response: WorkflowView; requiresIdempotency: false; };
  get_workflow_events: { method: "GET"; path: "/v1/workflows/{workflow_id}/events"; pathParams: { workflow_id: string; }; queryParams: Record<never, never>; body: never; response: ReadableStream<Uint8Array>; requiresIdempotency: false; };
  health: { method: "GET"; path: "/health"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: never; response: HealthResponse; requiresIdempotency: false; };
  list_decision_requests: { method: "GET"; path: "/v1/decision-requests"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: never; response: DecisionIndexView; requiresIdempotency: false; };
  lock_purchase_intent: { method: "POST"; path: "/v1/decisions/{decision_id}/purchase-intents"; pathParams: { decision_id: string; }; queryParams: Record<never, never>; body: PurchaseIntentCreate; response: PurchaseIntentView; requiresIdempotency: true; };
  open_payment_handoff: { method: "POST"; path: "/v1/payment-handoffs/{handoff_id}/open"; pathParams: { handoff_id: string; }; queryParams: Record<never, never>; body: never; response: PaymentHandoffView; requiresIdempotency: true; };
  propose_exchange_offer: { method: "POST"; path: "/v1/exchange-cases/{case_id}/offers"; pathParams: { case_id: string; }; queryParams: { route: string; }; body: ExchangeOfferCreate; response: ExchangeProjectionView; requiresIdempotency: true; };
  publish_exchange_evidence: { method: "POST"; path: "/v1/exchange-cases/{case_id}/evidence"; pathParams: { case_id: string; }; queryParams: { route: string; }; body: ExchangeEvidencePublish; response: ExchangeProjectionView; requiresIdempotency: true; };
  purchase_status: { method: "GET"; path: "/v1/purchase-intents/{intent_id}/status"; pathParams: { intent_id: string; }; queryParams: Record<never, never>; body: never; response: PurchaseStatusView; requiresIdempotency: false; };
  qualification_create_company_context: { method: "POST"; path: "/v1/qualification/company-context"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: CompanyContextCreate; response: QualificationMutationView; requiresIdempotency: true; };
  qualification_create_introduction: { method: "POST"; path: "/v1/qualification/engagements/{engagement_id}/introduction"; pathParams: { engagement_id: string; }; queryParams: Record<never, never>; body: QualificationIntroductionCreate; response: QualificationMutationView; requiresIdempotency: true; };
  qualification_create_mission: { method: "POST"; path: "/v1/qualification/missions"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: QualificationMissionCreate; response: QualificationMutationView; requiresIdempotency: true; };
  qualification_decide_approval: { method: "POST"; path: "/v1/qualification/decisions/{decision_id}/approval"; pathParams: { decision_id: string; }; queryParams: Record<never, never>; body: QualificationApprovalCreate; response: QualificationMutationView; requiresIdempotency: true; };
  qualification_get_company_context: { method: "GET"; path: "/v1/qualification/company-context/{item_id}"; pathParams: { item_id: string; }; queryParams: Record<never, never>; body: never; response: CompanyContextView; requiresIdempotency: false; };
  qualification_get_engagement: { method: "GET"; path: "/v1/qualification/engagements/{engagement_id}"; pathParams: { engagement_id: string; }; queryParams: Record<never, never>; body: never; response: QualificationEngagementView; requiresIdempotency: false; };
  qualification_get_inbox: { method: "GET"; path: "/v1/qualification/inbox"; pathParams: Record<never, never>; queryParams: { limit?: number; }; body: never; response: QualificationInboxView; requiresIdempotency: false; };
  qualification_get_integrity: { method: "GET"; path: "/v1/qualification/missions/{mission_id}/integrity"; pathParams: { mission_id: string; }; queryParams: Record<never, never>; body: never; response: QualificationIntegrityView; requiresIdempotency: false; };
  qualification_get_marketplace_product: { method: "GET"; path: "/v1/qualification/marketplace/products/{product_id}"; pathParams: { product_id: string; }; queryParams: Record<never, never>; body: never; response: PublicMarketplaceProductView; requiresIdempotency: false; };
  qualification_get_mission: { method: "GET"; path: "/v1/qualification/missions/{mission_id}"; pathParams: { mission_id: string; }; queryParams: Record<never, never>; body: never; response: QualificationMissionView; requiresIdempotency: false; };
  qualification_get_mission_events: { method: "GET"; path: "/v1/qualification/missions/{mission_id}/events"; pathParams: { mission_id: string; }; queryParams: { after?: string | null; limit?: number; }; body: never; response: QualificationEventFeed; requiresIdempotency: false; };
  qualification_get_workspace_analytics: { method: "GET"; path: "/v1/qualification/analytics"; pathParams: Record<never, never>; queryParams: { days?: number; }; body: never; response: WorkspaceAnalyticsView; requiresIdempotency: false; };
  qualification_get_workspace_settings: { method: "GET"; path: "/v1/qualification/settings"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: never; response: WorkspaceSettingsView; requiresIdempotency: false; };
  qualification_list_company_context: { method: "GET"; path: "/v1/qualification/company-context"; pathParams: Record<never, never>; queryParams: { include_retired?: boolean; }; body: never; response: CompanyContextList; requiresIdempotency: false; };
  qualification_record_consent: { method: "POST"; path: "/v1/qualification/engagements/{engagement_id}/consents"; pathParams: { engagement_id: string; }; queryParams: Record<never, never>; body: QualificationConsentCreate; response: QualificationMutationView; requiresIdempotency: true; };
  qualification_record_seller_response: { method: "POST"; path: "/v1/qualification/engagements/{engagement_id}/responses"; pathParams: { engagement_id: string; }; queryParams: Record<never, never>; body: QualificationSellerResponseCreate; response: QualificationMutationView; requiresIdempotency: true; };
  qualification_retire_company_context: { method: "POST"; path: "/v1/qualification/company-context/{item_id}/retire"; pathParams: { item_id: string; }; queryParams: Record<never, never>; body: never; response: QualificationMutationView; requiresIdempotency: true; };
  qualification_search_marketplace: { method: "GET"; path: "/v1/qualification/marketplace/search"; pathParams: Record<never, never>; queryParams: { category: string; query: string; limit?: number; }; body: never; response: PublicMarketplaceSearchView; requiresIdempotency: false; };
  qualification_update_company_context: { method: "PUT"; path: "/v1/qualification/company-context/{item_id}"; pathParams: { item_id: string; }; queryParams: Record<never, never>; body: CompanyContextUpdate; response: QualificationMutationView; requiresIdempotency: true; };
  qualification_update_workspace_settings: { method: "PUT"; path: "/v1/qualification/settings"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: WorkspaceSettingsUpdate; response: QualificationMutationView; requiresIdempotency: true; };
  ready: { method: "GET"; path: "/ready"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: never; response: HealthResponse; requiresIdempotency: false; };
  record_consent: { method: "POST"; path: "/v1/engagements/{engagement_id}/consent"; pathParams: { engagement_id: string; }; queryParams: Record<never, never>; body: ConsentCreate; response: EngagementView; requiresIdempotency: true; };
  record_purchase_outcome: { method: "POST"; path: "/v1/purchase-intents/{intent_id}/outcome-checkpoints"; pathParams: { intent_id: string; }; queryParams: Record<never, never>; body: OutcomeCheckpointCreate; response: OutcomeCheckpointView; requiresIdempotency: true; };
  record_solution_option_feedback: { method: "POST"; path: "/v1/decision-requests/{request_id}/solution-options/{solution_plan_id}/actions"; pathParams: { request_id: string; solution_plan_id: string; }; queryParams: Record<never, never>; body: OptionFeedbackCreate; response: OptionFeedbackView; requiresIdempotency: true; };
  reject_approval: { method: "POST"; path: "/v1/approval-requests/{approval_id}/reject"; pathParams: { approval_id: string; }; queryParams: Record<never, never>; body: ApprovalRejectCreate; response: ApprovalRequestView; requiresIdempotency: true; };
  reject_rule_proposal: { method: "POST"; path: "/v1/decision-rules/{rules_id}/proposals/{proposal_id}/reject"; pathParams: { rules_id: string; proposal_id: string; }; queryParams: Record<never, never>; body: ProposalDecisionCreate; response: ProposalDecisionView; requiresIdempotency: true; };
  replay_evaluation: { method: "POST"; path: "/v1/evaluation-runs/{evaluation_run_id}/replay"; pathParams: { evaluation_run_id: string; }; queryParams: Record<never, never>; body: never; response: EvaluationReplayView; requiresIdempotency: false; };
  reset_demo: { method: "POST"; path: "/v1/demo/reset"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: never; response: { [key: string]: unknown; }; requiresIdempotency: false; };
  revoke_approval: { method: "POST"; path: "/v1/approval-requests/{approval_id}/revoke"; pathParams: { approval_id: string; }; queryParams: Record<never, never>; body: ApprovalRevokeCreate; response: ApprovalRequestView; requiresIdempotency: true; };
  run_decision_calibration: { method: "POST"; path: "/v1/decision-requests/{request_id}/calibration-runs"; pathParams: { request_id: string; }; queryParams: Record<never, never>; body: CalibrationRunCreate; response: CalibrationRunView; requiresIdempotency: true; };
  select_action_plan: { method: "POST"; path: "/v1/decisions/{decision_id}/plan-selections"; pathParams: { decision_id: string; }; queryParams: Record<never, never>; body: PlanSelectionCreate; response: PlanSelectionView; requiresIdempotency: true; };
  seller_evidence_activity_metrics: { method: "GET"; path: "/v1/seller/products/{product_id}/activity-metrics"; pathParams: { product_id: string; }; queryParams: Record<never, never>; body: never; response: SellerActivityMetrics; requiresIdempotency: false; };
  seller_evidence_attach_evidence: { method: "POST"; path: "/v1/seller/pack-drafts/{draft_id}/evidence"; pathParams: { draft_id: string; }; queryParams: Record<never, never>; body: SellerEvidenceAttachCreate; response: SellerEvidenceAttachmentView; requiresIdempotency: true; };
  seller_evidence_claim_product: { method: "POST"; path: "/v1/seller/products/{product_id}/claim"; pathParams: { product_id: string; }; queryParams: Record<never, never>; body: SellerClaimCreate; response: SellerClaimView; requiresIdempotency: true; };
  seller_evidence_exports: { method: "GET"; path: "/v1/seller/pack-versions/{version_id}/exports"; pathParams: { version_id: string; }; queryParams: Record<never, never>; body: never; response: SellerPackExportsView; requiresIdempotency: false; };
  seller_evidence_get_draft: { method: "GET"; path: "/v1/seller/pack-drafts/{draft_id}"; pathParams: { draft_id: string; }; queryParams: Record<never, never>; body: never; response: SellerPackDraftView; requiresIdempotency: false; };
  seller_evidence_patch_draft: { method: "PATCH"; path: "/v1/seller/pack-drafts/{draft_id}"; pathParams: { draft_id: string; }; queryParams: Record<never, never>; body: SellerPackDraftPatch; response: SellerPackDraftView; requiresIdempotency: true; };
  seller_evidence_product_view: { method: "GET"; path: "/v1/seller/products/{product_id}/view"; pathParams: { product_id: string; }; queryParams: Record<never, never>; body: never; response: SellerEvidenceView; requiresIdempotency: false; };
  seller_evidence_publish: { method: "POST"; path: "/v1/seller/pack-drafts/{draft_id}/publish"; pathParams: { draft_id: string; }; queryParams: Record<never, never>; body: SellerPublishCreate; response: SellerPackVersionView; requiresIdempotency: true; };
  seller_evidence_review_decision: { method: "POST"; path: "/v1/seller/pack-drafts/{draft_id}/review-decisions"; pathParams: { draft_id: string; }; queryParams: Record<never, never>; body: SellerReviewDecisionCreate; response: SellerReviewDecisionView; requiresIdempotency: true; };
  seller_evidence_search_products: { method: "GET"; path: "/v1/seller/products/search"; pathParams: Record<never, never>; queryParams: { q?: string | null; }; body: never; response: SellerProductSearchView; requiresIdempotency: false; };
  seller_evidence_submit_review: { method: "POST"; path: "/v1/seller/pack-drafts/{draft_id}/submit-review"; pathParams: { draft_id: string; }; queryParams: Record<never, never>; body: SellerSubmitReviewCreate; response: SellerPackDraftView; requiresIdempotency: true; };
  seller_evidence_suspend: { method: "POST"; path: "/v1/seller/pack-versions/{version_id}/suspend"; pathParams: { version_id: string; }; queryParams: Record<never, never>; body: SellerSuspendCreate; response: SellerPackVersionView; requiresIdempotency: true; };
  seller_evidence_upload_evidence: { method: "POST"; path: "/v1/seller/pack-drafts/{draft_id}/evidence/upload"; pathParams: { draft_id: string; }; queryParams: Record<never, never>; body: FormData; response: SellerEvidenceAttachmentView; requiresIdempotency: true; };
  simulate_decision: { method: "POST"; path: "/v1/decisions/{decision_id}/simulations"; pathParams: { decision_id: string; }; queryParams: Record<never, never>; body: DecisionSimulationCreate; response: DecisionSimulationView; requiresIdempotency: true; };
  start_action_run: { method: "POST"; path: "/v1/decisions/{decision_id}/action-runs"; pathParams: { decision_id: string; }; queryParams: Record<never, never>; body: ActionRunCreate; response: ActionRunView; requiresIdempotency: true; };
  workspace_capabilities: { method: "GET"; path: "/v1/capabilities"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: never; response: CapabilityView[]; requiresIdempotency: false; };
  workspace_catalog: { method: "GET"; path: "/v1/workspace/catalog"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: never; response: CatalogProductView[]; requiresIdempotency: false; };
  workspace_chat: { method: "POST"; path: "/v1/workspace/chat"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: WorkspaceChatCreate; response: WorkspaceChatView; requiresIdempotency: false; };
  workspace_connectors: { method: "GET"; path: "/v1/workspace/connectors"; pathParams: Record<never, never>; queryParams: Record<never, never>; body: never; response: ConnectorView[]; requiresIdempotency: false; };
  workspace_conversations: { method: "GET"; path: "/v1/workspace/conversations"; pathParams: Record<never, never>; queryParams: { mode: "sira" | "seil"; }; body: never; response: WorkspaceConversationView[]; requiresIdempotency: false; };
  workspace_mission: { method: "GET"; path: "/v1/workspace/missions/{mission_id}"; pathParams: { mission_id: string; }; queryParams: Record<never, never>; body: never; response: MissionSnapshotView; requiresIdempotency: false; };
  workspace_product: { method: "GET"; path: "/v1/workspace/catalog/{product_id}"; pathParams: { product_id: string; }; queryParams: Record<never, never>; body: never; response: CatalogProductView; requiresIdempotency: false; };
}

export type OperationId = keyof Operations;
