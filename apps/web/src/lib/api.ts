export type ProjectStatus = "active" | "paused" | "killed" | "launched" | "archived";
export type ProjectStage =
  | "draft_idea"
  | "structured_intake"
  | "brief_generated"
  | "competitors_analyzed"
  | "assumptions_identified"
  | "validation_plan_created"
  | "experiment_running"
  | "decision_ready"
  | "paused"
  | "killed"
  | "proceeding";
export type RecommendationConfidence = "low" | "medium" | "high";

export type ProjectThesis = {
  id: string;
  version: number;
  thesis_text: string;
  rationale: string | null;
  confidence_score: string | null;
  created_at: string;
};

export type CustomerSegment = {
  id: string;
  project_id: string;
  name: string;
  description: string | null;
  buyer_type: "consumer" | "prosumer" | "smb" | "midmarket" | "enterprise" | "unknown" | null;
  priority: "primary" | "secondary" | "rejected" | "unknown" | null;
  confidence_score: string | null;
  created_at: string;
  updated_at: string;
};

export type Problem = {
  id: string;
  project_id: string;
  segment_id: string | null;
  description: string;
  severity: "low" | "medium" | "high" | "critical" | "unknown" | null;
  frequency: string | null;
  current_alternatives: string | null;
  confidence_score: string | null;
  created_at: string;
  updated_at: string;
};

export type Project = {
  id: string;
  workspace_id: string;
  name: string;
  short_description: string | null;
  status: ProjectStatus;
  current_thesis_id: string | null;
  confidence_score: string | null;
  created_at: string;
  updated_at: string;
  current_thesis: ProjectThesis | null;
  customer_segments: CustomerSegment[];
  problems: Problem[];
};

export type Me = {
  user: {
    id: string;
    email: string;
    display_name: string | null;
    created_at: string;
  };
  workspace: {
    id: string;
    name: string;
    created_at: string;
  };
  role: string;
};

export type CreateProjectInput = {
  name: string;
  short_description?: string;
  initial_thesis?: string;
};

export type BuyerType = "consumer" | "prosumer" | "smb" | "midmarket" | "enterprise" | "unknown";

export type StructuredProjectIntake = {
  project_name: string;
  one_sentence_summary: string;
  target_users: string[];
  buyer_type: BuyerType;
  problem_hypotheses: string[];
  proposed_solution: string;
  market_category: string | null;
  business_model_guess: string | null;
  suspected_competitors: string[];
  key_uncertainties: string[];
  clarifying_questions: string[];
};

export type ClarifyingAnswer = {
  question: string;
  answer: string;
};

export type AnalyzeIntakeInput = {
  raw_idea: string;
  user_background?: string;
  target_market_guess?: string;
  constraints?: string;
};

export type AnswerIntakeInput = {
  raw_idea: string;
  initial_intake?: StructuredProjectIntake;
  answers: ClarifyingAnswer[];
};

export type FinalizeIntakeInput = {
  structured_intake: StructuredProjectIntake;
  raw_idea?: string;
  answers?: ClarifyingAnswer[];
};

export type StructuredIntakeRun = {
  ai_run_id: string;
  ai_step_id: string;
  prompt_version: string;
  model_provider: string;
  model_name: string;
  used_stub: boolean;
  total_tokens: number | null;
  total_cost: string | null;
  intake: StructuredProjectIntake;
};

export type ProjectIntake = {
  id: string;
  project_id: string;
  ai_run_id: string | null;
  project_name: string;
  one_sentence_summary: string;
  target_users: string[];
  buyer_type: BuyerType;
  problem_hypotheses: string[];
  proposed_solution: string;
  market_category: string | null;
  business_model_guess: string | null;
  suspected_competitors: string[];
  key_uncertainties: string[];
  clarifying_questions: string[];
  user_answers: ClarifyingAnswer[];
  raw_idea: string | null;
  created_at: string;
};

export type StructuredIntakeFinalizeResult = {
  ai_run_id: string;
  ai_step_id: string;
  prompt_version: string;
  project: Project;
  intake_record: ProjectIntake;
  customer_segments: CustomerSegment[];
  problems: Problem[];
};

export type EvidenceSourceType = "url" | "file" | "note" | "transcript" | "manual";
export type EvidenceIngestionStatus = "pending" | "processing" | "ready" | "failed";
export type RetrievalMode = "semantic" | "keyword" | "hybrid";

export type EvidenceSource = {
  id: string;
  project_id: string;
  source_type: EvidenceSourceType;
  title: string | null;
  url: string | null;
  object_storage_key: string | null;
  summary: string | null;
  source_date: string | null;
  ingested_at: string | null;
  classification: string | null;
  credibility_score: string | null;
  ingestion_status: EvidenceIngestionStatus;
  ingestion_error: string | null;
  created_at: string;
  updated_at: string;
  chunk_count: number;
  text_preview: string | null;
};

export type AddEvidenceUrlInput = {
  url: string;
  title?: string;
};

export type AddEvidenceNoteInput = {
  title: string;
  text: string;
  source_type?: "note" | "transcript" | "manual";
  source_date?: string;
};

export type RetrieveEvidenceInput = {
  query: string;
  mode?: RetrievalMode;
  top_k?: number;
  source_types?: EvidenceSourceType[];
  freshness_days?: number;
};

export type EvidenceRetrievalResult = {
  source_id: string;
  chunk_id: string;
  title: string | null;
  url: string | null;
  source_type: EvidenceSourceType;
  chunk_index: number;
  text: string;
  score: number;
  semantic_score: number;
  keyword_score: number;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type EvidenceRetrieveResult = {
  ai_run_id: string;
  ai_step_id: string;
  mode: RetrievalMode;
  query: string;
  results: EvidenceRetrievalResult[];
};

export type ArtifactType =
  | "opportunity_brief"
  | "competitor_landscape"
  | "validation_plan"
  | "decision_memo"
  | "research_memo"
  | "customer_discovery_summary"
  | "other";

export type ClaimEvidenceLink = {
  id: string;
  evidence_source_id: string;
  evidence_chunk_id: string | null;
  relevance_score: string | null;
  quote: string | null;
  created_at: string;
};

export type Claim = {
  id: string;
  project_id: string;
  artifact_version_id: string | null;
  text: string;
  claim_type: string | null;
  confidence_score: string | null;
  support_level: "supported" | "partial" | "unsupported" | "inference";
  created_at: string;
  evidence_links: ClaimEvidenceLink[];
};

export type ArtifactVersion = {
  id: string;
  artifact_id: string;
  version: number;
  markdown_content: string;
  structured_content: Record<string, unknown>;
  generated_by_ai_run_id: string | null;
  langsmith_trace_id: string | null;
  langsmith_trace_url: string | null;
  created_at: string;
  claims: Claim[];
};

export type Artifact = {
  id: string;
  project_id: string;
  artifact_type: ArtifactType;
  title: string;
  current_version_id: string | null;
  created_at: string;
  updated_at: string;
  current_version: ArtifactVersion | null;
  versions: ArtifactVersion[];
};

export type Assumption = {
  id: string;
  project_id: string;
  text: string;
  category: string | null;
  importance: "low" | "medium" | "high" | "critical";
  uncertainty: "low" | "medium" | "high";
  kill_risk: boolean;
  confidence_score: string | null;
  status: "untested" | "testing" | "validated" | "invalidated" | "inconclusive";
  recommended_test: string | null;
  created_at: string;
  updated_at: string;
  evidence_links: {
    id: string;
    assumption_id: string;
    evidence_source_id: string;
    evidence_chunk_id: string | null;
    relevance_score: string | null;
    quote: string | null;
    created_at: string;
  }[];
};

export type Risk = {
  id: string;
  project_id: string;
  text: string;
  category: string | null;
  severity: "low" | "medium" | "high" | "critical";
  likelihood: "low" | "medium" | "high" | "unknown";
  mitigation: string | null;
  status: "open" | "mitigated" | "accepted" | "closed";
  created_at: string;
  updated_at: string;
};

export type AssumptionExtractionResult = {
  ai_run_id: string;
  ai_step_id: string;
  prompt_version: string;
  model_provider: string;
  model_name: string;
  used_stub: boolean;
  total_tokens: number | null;
  total_cost: string | null;
  assumptions: Assumption[];
  risks: Risk[];
};

export type UpdateAssumptionInput = {
  text?: string;
  category?: string | null;
  importance?: Assumption["importance"];
  uncertainty?: Assumption["uncertainty"];
  kill_risk?: boolean;
  confidence_score?: number | null;
  status?: Assumption["status"];
  recommended_test?: string | null;
};

export type ExperimentStatus = "planned" | "running" | "completed" | "cancelled";
export type ExperimentOutcome = "positive" | "negative" | "mixed" | "inconclusive";

export type ExperimentResult = {
  id: string;
  project_id: string;
  experiment_id: string;
  result_summary: string;
  outcome: ExperimentOutcome;
  confidence_delta: string | null;
  raw_notes: string | null;
  created_by: string | null;
  created_at: string;
};

export type Experiment = {
  id: string;
  project_id: string;
  assumption_id: string | null;
  name: string;
  method: string | null;
  plan: string | null;
  success_criteria: string | null;
  failure_threshold: string | null;
  status: ExperimentStatus;
  created_at: string;
  updated_at: string;
  results: ExperimentResult[];
};

export type GenerateValidationPlanInput = {
  assumption_ids?: string[];
  max_plans?: number;
};

export type ValidationPlanGenerateResult = {
  ai_run_id: string;
  ai_step_id: string;
  prompt_version: string;
  model_provider: string;
  model_name: string;
  used_stub: boolean;
  total_tokens: number | null;
  total_cost: string | null;
  artifact: Artifact;
  experiments: Experiment[];
};

export type LogExperimentResultInput = {
  result_summary: string;
  outcome: ExperimentOutcome;
  confidence_delta?: number;
  raw_notes?: string;
};

export type LogExperimentResultResult = {
  result: ExperimentResult;
  experiment: Experiment;
  assumption: Assumption | null;
  project_confidence_score: string | null;
};

export type DecisionType =
  | "build"
  | "pivot"
  | "pause"
  | "kill"
  | "change_icp"
  | "change_positioning"
  | "run_experiment"
  | "other";

export type DecisionLink = {
  id: string;
  decision_id: string;
  linked_type: "evidence" | "assumption" | "risk" | "artifact" | "competitor" | "experiment";
  linked_id: string;
  created_at: string;
};

export type Decision = {
  id: string;
  project_id: string;
  decision_type: DecisionType;
  title: string;
  rationale: string | null;
  expected_outcome: string | null;
  review_date: string | null;
  created_by: string | null;
  created_at: string;
  links: DecisionLink[];
};

export type CreateDecisionInput = {
  decision_type: DecisionType;
  title: string;
  rationale?: string;
  expected_outcome?: string;
  review_date?: string;
  linked_assumption_ids?: string[];
  linked_risk_ids?: string[];
  linked_evidence_source_ids?: string[];
  linked_artifact_ids?: string[];
  linked_competitor_ids?: string[];
  linked_experiment_ids?: string[];
};

export type Citation = {
  source_id: string;
  chunk_id: string | null;
  title: string | null;
  url: string | null;
  quote: string | null;
  retrieved_at: string | null;
  relevance_score: number | null;
};

export type OpportunityBriefGenerateResult = {
  ai_run_id: string;
  ai_step_id: string;
  prompt_version: string;
  model_provider: string;
  model_name: string;
  used_stub: boolean;
  total_tokens: number | null;
  total_cost: string | null;
  retrieval_result_count: number;
  artifact: Artifact;
  version: ArtifactVersion;
  claims: Claim[];
  assumptions: Assumption[];
  risks: Risk[];
  citations: Citation[];
  unsupported_claims: string[];
};

export type CompetitorCategory =
  | "direct"
  | "adjacent"
  | "incumbent"
  | "substitute"
  | "manual_alternative"
  | "unknown";

export type CompetitorThreatLevel = "low" | "medium" | "high" | "unknown";

export type CompetitorEvidenceLink = {
  id: string;
  evidence_source_id: string;
  evidence_chunk_id: string | null;
  created_at: string;
};

export type Competitor = {
  id: string;
  project_id: string;
  name: string;
  url: string | null;
  category: CompetitorCategory;
  target_user: string | null;
  positioning: string | null;
  pricing_summary: string | null;
  key_features: string[];
  strengths: string | null;
  weaknesses: string | null;
  differentiation_notes: string | null;
  threat_level: CompetitorThreatLevel;
  watchlist_status: string;
  last_analyzed_at: string | null;
  created_at: string;
  updated_at: string;
  evidence_links: CompetitorEvidenceLink[];
};

export type CreateCompetitorInput = {
  name: string;
  url?: string;
  category?: CompetitorCategory;
};

export type AnalyzeCompetitorsInput = {
  seed_competitors?: CreateCompetitorInput[];
  ingest_urls?: boolean;
};

export type CompetitorAnalysisResult = {
  ai_run_id: string;
  ai_step_id: string;
  prompt_version: string;
  model_provider: string;
  model_name: string;
  used_stub: boolean;
  total_tokens: number | null;
  total_cost: string | null;
  retrieval_result_count: number;
  ingested_source_count: number;
  artifact: Artifact;
  competitors: Competitor[];
  claims: Claim[];
  citations: Citation[];
  unsupported_claims: string[];
};

export type WorkflowStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "waiting_for_human";

export type WorkflowStep = {
  id: string;
  ai_run_id: string;
  step_name: string;
  status: string;
  output_json: Record<string, unknown> | null;
  latency_ms: number | null;
  tokens: number | null;
  cost: string | null;
  langsmith_trace_id: string | null;
  langsmith_run_id: string | null;
  langsmith_trace_url: string | null;
  error: string | null;
  created_at: string;
};

export type WorkflowRun = {
  id: string;
  project_id: string | null;
  workflow_type: string;
  status: WorkflowStatus;
  model_provider: string | null;
  model_name: string | null;
  prompt_version: string | null;
  input_summary: string | null;
  output_summary: string | null;
  total_tokens: number | null;
  total_cost: string | null;
  langsmith_trace_id: string | null;
  langsmith_trace_url: string | null;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  steps: WorkflowStep[];
};

export type ResearchPlanStatus = "draft" | "approved" | "rejected" | "completed";
export type ResearchSprintStatus =
  | "planned"
  | "waiting_for_approval"
  | "approved"
  | "running"
  | "needs_review"
  | "waiting_for_memory_approval"
  | "completed"
  | "failed"
  | "cancelled"
  | "rejected";
export type DiscoveredSourceType =
  | "company_site"
  | "pricing_page"
  | "product_page"
  | "review"
  | "forum"
  | "blog"
  | "market_report"
  | "directory"
  | "docs"
  | "unknown";
export type DiscoveredSourceStatus = "candidate" | "approved" | "rejected" | "ingested" | "failed";
export type CompetitorCandidateCategory =
  | "direct_competitor"
  | "indirect_competitor"
  | "substitute_behavior"
  | "incumbent_platform"
  | "adjacent_solution"
  | "irrelevant";
export type CompetitorCandidateStatus = "candidate" | "approved" | "rejected" | "merged";
export type CompetitorCandidateThreatLevel = "low" | "medium" | "high";

export type ResearchPlan = {
  id: string;
  project_id: string;
  ai_run_id: string | null;
  objective: string;
  target_customer_hypotheses: string[];
  research_questions: string[];
  competitor_queries: string[];
  market_queries: string[];
  substitute_queries: string[];
  source_types: string[];
  assumptions_to_test: string[];
  expected_outputs: string[];
  status: ResearchPlanStatus;
  approved_at: string | null;
  rejected_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ResearchSprint = {
  id: string;
  project_id: string;
  research_plan_id: string;
  ai_run_id: string | null;
  status: ResearchSprintStatus;
  temporal_workflow_id: string | null;
  temporal_run_id: string | null;
  current_step: string | null;
  failed_step: string | null;
  failure_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  langsmith_trace_id: string | null;
  langsmith_trace_url: string | null;
  created_at: string;
  updated_at: string;
  plan: ResearchPlan;
};

export type ResearchSprintPlanInput = {
  objective?: string;
};

export type ResearchPlanUpdateInput = Partial<
  Pick<
    ResearchPlan,
    | "objective"
    | "target_customer_hypotheses"
    | "research_questions"
    | "competitor_queries"
    | "market_queries"
    | "substitute_queries"
    | "source_types"
    | "assumptions_to_test"
    | "expected_outputs"
  >
>;

export type ResearchSprintPlanRun = {
  ai_run_id: string;
  ai_step_id: string;
  prompt_version: string;
  model_provider: string;
  model_name: string;
  used_stub: boolean;
  total_tokens: number | null;
  total_cost: string | null;
  sprint: ResearchSprint;
};

export type ResearchSprintApproval = {
  ai_run_id: string | null;
  sprint: ResearchSprint;
};

export type ResearchSprintExecution = {
  sprint: ResearchSprint;
  temporal_enabled: boolean;
  temporal_workflow_id: string | null;
  temporal_run_id: string | null;
  status: ResearchSprintStatus;
  current_step: string | null;
  failed_step: string | null;
  failure_message: string | null;
  action_required: string | null;
};

export type ResearchSprintExecutionAction = {
  sprint: ResearchSprint;
  action: "started" | "cancelled" | "retried" | "signaled";
  temporal_workflow_id: string | null;
};

export type DiscoveredSource = {
  id: string;
  project_id: string;
  research_sprint_id: string;
  evidence_source_id: string | null;
  url: string;
  title: string | null;
  snippet: string | null;
  source_type: DiscoveredSourceType;
  relevance_score: string;
  reason_selected: string;
  associated_research_question: string | null;
  status: DiscoveredSourceStatus;
  ingestion_error: string | null;
  ingested_at: string | null;
  created_at: string;
  updated_at: string;
};

export type SourceDiscoveryRun = {
  ai_run_id: string;
  ai_step_id: string;
  generated_count: number;
  candidate_count: number;
  sources: DiscoveredSource[];
};

export type CompetitorCandidate = {
  id: string;
  project_id: string;
  research_sprint_id: string;
  competitor_id: string | null;
  evidence_source_id: string | null;
  name: string;
  url: string | null;
  category: CompetitorCandidateCategory;
  target_user: string | null;
  positioning: string | null;
  pricing_signal: string | null;
  core_features: string[];
  why_it_matters: string;
  threat_level: CompetitorCandidateThreatLevel;
  relevance_score: string;
  source_ids: string[];
  status: CompetitorCandidateStatus;
  ingestion_error: string | null;
  ingested_at: string | null;
  created_at: string;
  updated_at: string;
};

export type CompetitorCandidateUpdateInput = Partial<
  Pick<
    CompetitorCandidate,
    | "name"
    | "url"
    | "category"
    | "target_user"
    | "positioning"
    | "pricing_signal"
    | "core_features"
    | "why_it_matters"
    | "threat_level"
  >
> & {
  relevance_score?: number;
};

export type CompetitorDiscoveryRun = {
  ai_run_id: string;
  ai_step_id: string;
  generated_count: number;
  candidate_count: number;
  candidates: CompetitorCandidate[];
};

export type AgenticResearchRun = {
  ai_run_id: string;
  ai_step_id: string;
  prompt_version: string;
  model_provider: string;
  model_name: string;
  used_stub: boolean;
  total_tokens: number | null;
  total_cost: string | null;
  retrieval_tool_call_count: number;
  additional_retrieval_passes: number;
  evidence_gap_count: number;
  artifact: Artifact;
  version: ArtifactVersion;
  claims: Claim[];
  citations: Citation[];
  unsupported_claims: string[];
};

export type AgenticResearchApproval = {
  ai_run_id: string;
  ai_step_id: string;
  sprint: ResearchSprint;
  artifact: Artifact;
  version: ArtifactVersion;
};

export type ResearchHistoryEvent = {
  id: string;
  research_sprint_id: string;
  event_type:
    | "plan_created"
    | "plan_approved"
    | "plan_rejected"
    | "source_discovery"
    | "source_ingestion"
    | "competitor_discovery"
    | "competitor_merge"
    | "memo_generated"
    | "memory_update_approved"
    | "memory_update_rejected"
    | "sprint_completed"
    | "sprint_failed";
  title: string;
  summary: string;
  why_it_matters: string;
  related_entity_type:
    | "research_sprint"
    | "research_plan"
    | "artifact"
    | "artifact_version"
    | "evidence"
    | "competitor"
    | "assumption"
    | "risk"
    | "workflow";
  related_entity_id: string;
  created_at: string;
};

export type ResearchSprintHistory = {
  sprint: ResearchSprint;
  source_candidate_count: number;
  ingested_source_count: number;
  competitor_candidate_count: number;
  merged_competitor_count: number;
  memo_artifact_id: string | null;
  memo_version_id: string | null;
  memory_update_status: string | null;
  memory_update_summary: Record<string, unknown> | null;
  recommendation_change: string | null;
  events: ResearchHistoryEvent[];
};

export type ProjectResearchHistory = {
  project_id: string;
  sprint_count: number;
  completed_sprint_count: number;
  pending_review_sprint_count: number;
  latest_recommendation_change: string | null;
  sprints: ResearchSprintHistory[];
};

export type ToolRiskLevel = "low" | "medium" | "high";
export type ToolAccessMode = "read" | "write" | "proposal";
export type ToolApprovalPolicy = "never_required" | "required_for_write" | "always_required";
export type ToolInvocationStatus = "requested" | "approved" | "rejected" | "executed" | "failed";

export type AgentToolDefinition = {
  name: string;
  title: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  access_mode: ToolAccessMode;
  risk_level: ToolRiskLevel;
  approval_policy: ToolApprovalPolicy;
  allowed_project_roles: string[];
};

export type ToolInvocation = {
  id: string;
  project_id: string;
  research_sprint_id: string | null;
  tool_name: string;
  access_mode: ToolAccessMode;
  risk_level: ToolRiskLevel;
  input_json: Record<string, unknown>;
  output_json: Record<string, unknown> | null;
  output_summary: string | null;
  status: ToolInvocationStatus;
  requested_by: "agent" | "user" | "system";
  approved_by_user_id: string | null;
  created_at: string;
  updated_at: string;
  executed_at: string | null;
};

export type ApprovalRequestType =
  | "research_plan"
  | "memory_update"
  | "tool_invocation"
  | "validation_plan"
  | "decision";
export type ApprovalRequestStatus = "pending" | "approved" | "rejected" | "expired";
export type ApprovalRequestedBy = "agent" | "user" | "system";

export type ApprovalRequest = {
  id: string;
  project_id: string | null;
  request_type: ApprovalRequestType;
  status: ApprovalRequestStatus;
  requested_by: ApprovalRequestedBy;
  approved_by_user_id: string | null;
  risk_level: ToolRiskLevel;
  summary: string;
  proposed_change: Record<string, unknown> | null;
  entity_type: string | null;
  entity_id: string | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
};

export type AuditActorType = "user" | "agent" | "system";

export type AuditEvent = {
  id: string;
  project_id: string | null;
  user_id: string | null;
  event_type: string;
  actor_type: AuditActorType;
  entity_type: string | null;
  entity_id: string | null;
  summary: string | null;
  risk_level: ToolRiskLevel | null;
  event_metadata: Record<string, unknown>;
  created_at: string;
};

export type DemoSeedResult = {
  project: Project;
  created: boolean;
  counts: {
    evidence_sources: number;
    artifacts: number;
    competitors: number;
    assumptions: number;
    risks: number;
    experiments: number;
    experiment_results: number;
    decisions: number;
    ai_runs: number;
  };
  next_url: string;
  message: string;
};

export type MvpEvalCheck = {
  key: string;
  label: string;
  passed: boolean;
  observed: number | boolean | string | null;
  expected: string;
};

export type MvpEval = {
  project_id: string;
  passed: boolean;
  score: number;
  total: number;
  checks: MvpEvalCheck[];
};

export type ResearchEvalCase = {
  id: string;
  idea_type: string;
  idea: string;
  expected_competitor_types: string[];
  expected_risky_assumptions: string[];
  required_output_sections: string[];
  unacceptable_claims: string[];
  expected_next_action_type: string;
  demo_ready: boolean;
};

export type V1ResearchEvalMetric = {
  key: string;
  label: string;
  passed: boolean;
  observed: number | boolean | string | null;
  expected: string;
};

export type V1ResearchEval = {
  project_id: string;
  passed: boolean;
  score: number;
  total: number;
  metrics: V1ResearchEvalMetric[];
  dataset_cases: ResearchEvalCase[];
  dataset_case_count: number;
  demo_ready_case_count: number;
};

export type StrategicRecommendation = {
  id: string;
  project_id: string;
  recommendation: string;
  rationale: string;
  confidence: RecommendationConfidence;
  next_action_type: string;
  next_action_label: string;
  source_artifact_ids: string[];
  source_evidence_ids: string[];
  created_at: string;
};

export type NextBestAction = {
  action_type: string;
  label: string;
  description: string;
  why_it_matters: string;
  primary: boolean;
  related_stage: ProjectStage;
  target_route: string | null;
};

export type ReadinessItem = {
  key: string;
  label: string;
  status: "complete" | "missing" | "needs_work";
  related_action: string | null;
};

export type IdeaReadiness = {
  project_id: string;
  score: number;
  status: "not_ready" | "partially_ready" | "ready_for_validation" | "decision_ready";
  completed_items: ReadinessItem[];
  missing_items: ReadinessItem[];
  weakest_area: string;
  recommended_next_action: string;
};

export type StrategicSnapshot = {
  current_thesis: string | null;
  target_user: string | null;
  primary_problem: string | null;
  proposed_wedge: string | null;
  main_risk: string | null;
  current_confidence: RecommendationConfidence;
  current_stage: ProjectStage;
};

export type EvidenceHealth = {
  source_count: number;
  competitor_count: number;
  cited_claim_count: number;
  unsupported_claim_count: number;
  validated_assumption_count: number;
  weakest_evidence_area: string;
  last_evidence_update: string | null;
};

export type StrategicUpdate = {
  id: string;
  project_id: string;
  title: string;
  summary: string;
  why_it_matters: string;
  related_entity_type:
    | "artifact"
    | "evidence"
    | "competitor"
    | "assumption"
    | "experiment"
    | "decision"
    | "workflow";
  related_entity_id: string;
  created_at: string;
};

export type ProjectOverview = {
  project: Project;
  current_recommendation: StrategicRecommendation;
  next_best_action: NextBestAction;
  secondary_actions: NextBestAction[];
  idea_readiness: IdeaReadiness;
  strategic_snapshot: StrategicSnapshot;
  evidence_health: EvidenceHealth;
  recent_strategic_updates: StrategicUpdate[];
  key_assumptions: Assumption[];
  key_risks: Risk[];
};

export type AIProviderKeyStatus = {
  openai: boolean;
  anthropic: boolean;
  gemini: boolean;
  any_present: boolean;
};

export type LiteLLMReachabilityStatus = {
  base_url: string;
  endpoint: string;
  reachable: boolean;
  status_code: number | null;
  error: string | null;
};

export type AIStatusStructuredOutputCheck = {
  ok: boolean;
  used_stub: boolean | null;
  model_provider: string | null;
  model_name: string | null;
  total_tokens: number | null;
  total_cost: string | null;
  error: string | null;
};

export type AIStatus = {
  llm_stub_mode: "auto" | "always" | "never";
  llm_fallback_policy: "disabled" | "emergency" | "always";
  llm_structured_output_repair_attempts: number;
  resolved_mode: "stub" | "live";
  should_use_stub: boolean;
  litellm_model: string;
  litellm_base_url: string;
  litellm_reachability: LiteLLMReachabilityStatus;
  provider_keys: AIProviderKeyStatus;
  embedding_model: string;
  embedding_dimension: number;
  structured_output_healthcheck: AIStatusStructuredOutputCheck | null;
};

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  retryable: boolean;
  status: number | null;

  constructor(
    message: string,
    { retryable = false, status = null }: { retryable?: boolean; status?: number | null } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.retryable = retryable;
    this.status = status;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new ApiError(
      "Thesys could not reach the API. Check that the local services are running, then retry.",
      { retryable: true },
    );
  }

  if (!response.ok) {
    let message = statusFallbackMessage(response.status);
    try {
      const body = (await response.json()) as { detail?: unknown; message?: unknown };
      message = formatApiError(body, message);
    } catch {
      // Preserve the status-based fallback when the response is not JSON.
    }
    throw new ApiError(message, {
      retryable: isRetryableStatus(response.status),
      status: response.status,
    });
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

function statusFallbackMessage(status: number) {
  if (status === 400) {
    return "Thesys could not use that input. Review the highlighted fields and try again.";
  }
  if (status === 401) {
    return "Your session is not authorized. Sign in again, then retry.";
  }
  if (status === 403) {
    return "You do not have permission to perform this action.";
  }
  if (status === 404) {
    return "Thesys could not find that project or record.";
  }
  if (status === 408) {
    return "The request timed out. Retry when the service is responsive.";
  }
  if (status === 409) {
    return "The record changed before this action finished. Refresh and try again.";
  }
  if (status === 413) {
    return "That input is too large. Shorten it and try again.";
  }
  if (status === 422) {
    return "Some input is invalid. Review the fields and try again.";
  }
  if (status === 429) {
    return "Thesys is rate limited right now. Wait a moment, then retry.";
  }
  if (status >= 500) {
    return "The Thesys API hit a server error. Retry, or check the service logs if it repeats.";
  }
  return `Request failed with ${status}`;
}

function isRetryableStatus(status: number) {
  return status === 408 || status === 429 || status >= 500;
}

function formatApiError(body: { detail?: unknown; message?: unknown }, fallback: string) {
  return formatApiErrorDetail(body.detail) ?? formatApiErrorDetail(body.message) ?? fallback;
}

function formatApiErrorDetail(detail: unknown): string | null {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail.map(formatValidationIssue).filter(Boolean);
    return messages.length > 0 ? messages.join("; ") : null;
  }
  if (detail && typeof detail === "object") {
    return JSON.stringify(detail);
  }
  return null;
}

function formatValidationIssue(issue: unknown) {
  if (!issue || typeof issue !== "object") {
    return String(issue);
  }
  const record = issue as Record<string, unknown>;
  const message = typeof record.msg === "string" ? record.msg : JSON.stringify(record);
  const location = Array.isArray(record.loc)
    ? record.loc
        .filter((part) => part !== "body")
        .map(String)
        .join(".")
    : "";
  return location ? `${location}: ${message}` : message;
}

function normalizeOptionalUrl(value: string | undefined) {
  const trimmed = value?.trim();
  if (!trimmed) {
    return undefined;
  }
  if (/^[a-z][a-z\d+\-.]*:\/\//i.test(trimmed)) {
    return trimmed;
  }
  return `https://${trimmed}`;
}

export function getMe() {
  return apiFetch<Me>("/api/me");
}

export async function listProjects() {
  const response = await apiFetch<{ projects: Project[] }>("/api/projects");
  return response.projects;
}

export function createProject(input: CreateProjectInput) {
  return apiFetch<Project>("/api/projects", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function getProject(projectId: string) {
  return apiFetch<Project>(`/api/projects/${projectId}`);
}

export function getProjectOverview(projectId: string) {
  return apiFetch<ProjectOverview>(`/api/projects/${projectId}/overview`);
}

export function getIdeaReadiness(projectId: string) {
  return apiFetch<IdeaReadiness>(`/api/projects/${projectId}/readiness`);
}

export function getStrategicUpdates(projectId: string) {
  return apiFetch<StrategicUpdate[]>(`/api/projects/${projectId}/strategic-updates`);
}

export function executeNextAction(projectId: string) {
  return apiFetch<NextBestAction>(`/api/projects/${projectId}/next-action`, {
    method: "POST",
  });
}

export function analyzeProjectIntake(projectId: string, input: AnalyzeIntakeInput) {
  return apiFetch<StructuredIntakeRun>(`/api/projects/${projectId}/intake/analyze`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function answerProjectIntake(projectId: string, input: AnswerIntakeInput) {
  return apiFetch<StructuredIntakeRun>(`/api/projects/${projectId}/intake/answer`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function finalizeProjectIntake(projectId: string, input: FinalizeIntakeInput) {
  return apiFetch<StructuredIntakeFinalizeResult>(
    `/api/projects/${projectId}/intake/finalize`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export async function listEvidenceSources(projectId: string) {
  const response = await apiFetch<{ sources: EvidenceSource[] }>(
    `/api/projects/${projectId}/evidence`,
  );
  return response.sources;
}

export function addEvidenceUrl(projectId: string, input: AddEvidenceUrlInput) {
  return apiFetch<EvidenceSource>(`/api/projects/${projectId}/evidence/url`, {
    method: "POST",
    body: JSON.stringify({ ...input, url: normalizeOptionalUrl(input.url) ?? input.url }),
  });
}

export function addEvidenceNote(projectId: string, input: AddEvidenceNoteInput) {
  return apiFetch<EvidenceSource>(`/api/projects/${projectId}/evidence/note`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function uploadEvidenceFile(projectId: string, file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch<EvidenceSource>(`/api/projects/${projectId}/evidence/file`, {
    method: "POST",
    body: formData,
  });
}

export function retrieveEvidence(projectId: string, input: RetrieveEvidenceInput) {
  return apiFetch<EvidenceRetrieveResult>(`/api/projects/${projectId}/evidence/retrieve`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function reprocessEvidenceSource(projectId: string, sourceId: string) {
  return apiFetch<EvidenceSource>(
    `/api/projects/${projectId}/evidence/${sourceId}/reprocess`,
    {
      method: "POST",
    },
  );
}

export function deleteEvidenceSource(projectId: string, sourceId: string) {
  return apiFetch<void>(`/api/projects/${projectId}/evidence/${sourceId}`, {
    method: "DELETE",
  });
}

export async function listArtifacts(projectId: string, artifactType?: ArtifactType) {
  const query = artifactType ? `?artifact_type=${artifactType}` : "";
  const response = await apiFetch<{ artifacts: Artifact[] }>(
    `/api/projects/${projectId}/artifacts${query}`,
  );
  return response.artifacts;
}

export function generateOpportunityBrief(projectId: string) {
  return apiFetch<OpportunityBriefGenerateResult>(
    `/api/projects/${projectId}/artifacts/opportunity-brief/generate`,
    {
      method: "POST",
    },
  );
}

export async function listCompetitors(projectId: string) {
  const response = await apiFetch<{ competitors: Competitor[] }>(
    `/api/projects/${projectId}/competitors`,
  );
  return response.competitors;
}

export function createCompetitor(projectId: string, input: CreateCompetitorInput) {
  return apiFetch<Competitor>(`/api/projects/${projectId}/competitors`, {
    method: "POST",
    body: JSON.stringify({ ...input, url: normalizeOptionalUrl(input.url) }),
  });
}

export function analyzeCompetitors(projectId: string, input: AnalyzeCompetitorsInput = {}) {
  const seedCompetitors = input.seed_competitors?.map((competitor) => ({
    ...competitor,
    url: normalizeOptionalUrl(competitor.url),
  }));
  return apiFetch<CompetitorAnalysisResult>(`/api/projects/${projectId}/competitors/analyze`, {
    method: "POST",
    body: JSON.stringify({ ...input, seed_competitors: seedCompetitors }),
  });
}

export async function listAssumptions(projectId: string) {
  const response = await apiFetch<{ assumptions: Assumption[] }>(
    `/api/projects/${projectId}/assumptions`,
  );
  return response.assumptions;
}

export function extractAssumptions(projectId: string) {
  return apiFetch<AssumptionExtractionResult>(`/api/projects/${projectId}/assumptions/extract`, {
    method: "POST",
  });
}

export function updateAssumption(
  projectId: string,
  assumptionId: string,
  input: UpdateAssumptionInput,
) {
  return apiFetch<Assumption>(`/api/projects/${projectId}/assumptions/${assumptionId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export async function listRisks(projectId: string) {
  const response = await apiFetch<{ risks: Risk[] }>(`/api/projects/${projectId}/risks`);
  return response.risks;
}

export async function listExperiments(projectId: string) {
  const response = await apiFetch<{ experiments: Experiment[] }>(
    `/api/projects/${projectId}/experiments`,
  );
  return response.experiments;
}

export function generateValidationPlan(projectId: string, input: GenerateValidationPlanInput = {}) {
  return apiFetch<ValidationPlanGenerateResult>(
    `/api/projects/${projectId}/experiments/validation-plan`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function logExperimentResult(
  projectId: string,
  experimentId: string,
  input: LogExperimentResultInput,
) {
  return apiFetch<LogExperimentResultResult>(
    `/api/projects/${projectId}/experiments/${experimentId}/results`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export async function listDecisions(projectId: string) {
  const response = await apiFetch<{ decisions: Decision[] }>(
    `/api/projects/${projectId}/decisions`,
  );
  return response.decisions;
}

export function createDecision(projectId: string, input: CreateDecisionInput) {
  return apiFetch<Decision>(`/api/projects/${projectId}/decisions`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function seedDemoProject() {
  return apiFetch<DemoSeedResult>("/api/demo/seed", {
    method: "POST",
  });
}

export async function listProjectWorkflows(projectId: string, limit = 10) {
  const response = await apiFetch<{ runs: WorkflowRun[] }>(
    `/api/projects/${projectId}/workflows?limit=${limit}`,
  );
  return response.runs;
}

export async function listResearchSprints(projectId: string) {
  const response = await apiFetch<{ sprints: ResearchSprint[] }>(
    `/api/projects/${projectId}/research-sprints`,
  );
  return response.sprints;
}

export function startResearchSprintPlan(projectId: string, input: ResearchSprintPlanInput = {}) {
  return apiFetch<ResearchSprintPlanRun>(`/api/projects/${projectId}/research-sprints/plan`, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function updateResearchPlan(
  projectId: string,
  planId: string,
  input: ResearchPlanUpdateInput,
) {
  return apiFetch<ResearchPlan>(`/api/projects/${projectId}/research-plans/${planId}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
}

export function approveResearchSprint(
  projectId: string,
  sprintId: string,
  input: ResearchPlanUpdateInput = {},
) {
  return apiFetch<ResearchSprintApproval>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/approve`,
    {
      method: "POST",
      body: JSON.stringify(input),
    },
  );
}

export function rejectResearchSprint(projectId: string, sprintId: string) {
  return apiFetch<ResearchSprintApproval>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/reject`,
    {
      method: "POST",
    },
  );
}

export function getDurableResearchStatus(projectId: string, sprintId: string) {
  return apiFetch<ResearchSprintExecution>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/durable/status`,
  );
}

export function startDurableResearchWorkflow(projectId: string, sprintId: string) {
  return apiFetch<ResearchSprintExecutionAction>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/durable/start`,
    {
      method: "POST",
    },
  );
}

export function retryDurableResearchWorkflow(projectId: string, sprintId: string) {
  return apiFetch<ResearchSprintExecutionAction>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/durable/retry`,
    {
      method: "POST",
    },
  );
}

export function cancelDurableResearchWorkflow(projectId: string, sprintId: string) {
  return apiFetch<ResearchSprintExecutionAction>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/durable/cancel`,
    {
      method: "POST",
    },
  );
}

export async function listDiscoveredSources(projectId: string, sprintId: string) {
  const response = await apiFetch<{ sources: DiscoveredSource[] }>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/sources`,
  );
  return response.sources;
}

export function discoverSources(projectId: string, sprintId: string) {
  return apiFetch<SourceDiscoveryRun>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/sources/discover`,
    {
      method: "POST",
    },
  );
}

export async function approveDiscoveredSource(
  projectId: string,
  sprintId: string,
  sourceId: string,
) {
  const response = await apiFetch<{ source: DiscoveredSource }>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/sources/${sourceId}/approve`,
    {
      method: "POST",
    },
  );
  return response.source;
}

export async function rejectDiscoveredSource(
  projectId: string,
  sprintId: string,
  sourceId: string,
) {
  const response = await apiFetch<{ source: DiscoveredSource }>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/sources/${sourceId}/reject`,
    {
      method: "POST",
    },
  );
  return response.source;
}

export async function listCompetitorCandidates(projectId: string, sprintId: string) {
  const response = await apiFetch<{ candidates: CompetitorCandidate[] }>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/competitor-candidates`,
  );
  return response.candidates;
}

export function discoverCompetitorCandidates(projectId: string, sprintId: string) {
  return apiFetch<CompetitorDiscoveryRun>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/competitor-candidates/discover`,
    {
      method: "POST",
    },
  );
}

export function updateCompetitorCandidate(
  projectId: string,
  sprintId: string,
  candidateId: string,
  input: CompetitorCandidateUpdateInput,
) {
  return apiFetch<CompetitorCandidate>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/competitor-candidates/${candidateId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ ...input, url: normalizeOptionalUrl(input.url ?? undefined) }),
    },
  );
}

export async function approveCompetitorCandidate(
  projectId: string,
  sprintId: string,
  candidateId: string,
) {
  const response = await apiFetch<{ candidate: CompetitorCandidate }>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/competitor-candidates/${candidateId}/approve`,
    {
      method: "POST",
    },
  );
  return response.candidate;
}

export async function rejectCompetitorCandidate(
  projectId: string,
  sprintId: string,
  candidateId: string,
) {
  const response = await apiFetch<{ candidate: CompetitorCandidate }>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/competitor-candidates/${candidateId}/reject`,
    {
      method: "POST",
    },
  );
  return response.candidate;
}

export function runAgenticResearch(projectId: string, sprintId: string) {
  return apiFetch<AgenticResearchRun>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/agentic-rag/run`,
    {
      method: "POST",
    },
  );
}

export function approveAgenticResearchMemo(projectId: string, sprintId: string) {
  return apiFetch<AgenticResearchApproval>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/agentic-rag/approve`,
    {
      method: "POST",
    },
  );
}

export function rejectAgenticResearchMemo(projectId: string, sprintId: string) {
  return apiFetch<AgenticResearchApproval>(
    `/api/projects/${projectId}/research-sprints/${sprintId}/agentic-rag/reject`,
    {
      method: "POST",
    },
  );
}

export function getProjectResearchHistory(projectId: string) {
  return apiFetch<ProjectResearchHistory>(`/api/projects/${projectId}/research-history`);
}

export async function listAgentTools() {
  const response = await apiFetch<{ tools: AgentToolDefinition[] }>("/api/tools");
  return response.tools;
}

export async function listToolInvocations(projectId: string, researchSprintId?: string) {
  const params = researchSprintId
    ? `?research_sprint_id=${encodeURIComponent(researchSprintId)}`
    : "";
  const response = await apiFetch<{ invocations: ToolInvocation[] }>(
    `/api/projects/${projectId}/tool-invocations${params}`,
  );
  return response.invocations;
}

export async function approveToolInvocation(projectId: string, invocationId: string) {
  const response = await apiFetch<{ invocation: ToolInvocation }>(
    `/api/projects/${projectId}/tool-invocations/${invocationId}/approve`,
    { method: "POST" },
  );
  return response.invocation;
}

export async function rejectToolInvocation(projectId: string, invocationId: string) {
  const response = await apiFetch<{ invocation: ToolInvocation }>(
    `/api/projects/${projectId}/tool-invocations/${invocationId}/reject`,
    { method: "POST" },
  );
  return response.invocation;
}

export async function listApprovalRequests(
  projectId: string,
  statusFilter: ApprovalRequestStatus | "all" = "pending",
) {
  const params =
    statusFilter === "all"
      ? ""
      : `?status_filter=${encodeURIComponent(statusFilter)}`;
  const response = await apiFetch<{ approvals: ApprovalRequest[] }>(
    `/api/projects/${projectId}/approvals${params}`,
  );
  return response.approvals;
}

export async function approveApprovalRequest(projectId: string, approvalId: string) {
  const response = await apiFetch<{ approval: ApprovalRequest }>(
    `/api/projects/${projectId}/approvals/${approvalId}/approve`,
    { method: "POST" },
  );
  return response.approval;
}

export async function rejectApprovalRequest(projectId: string, approvalId: string) {
  const response = await apiFetch<{ approval: ApprovalRequest }>(
    `/api/projects/${projectId}/approvals/${approvalId}/reject`,
    { method: "POST" },
  );
  return response.approval;
}

export async function listAuditEvents(projectId: string) {
  const response = await apiFetch<{ events: AuditEvent[] }>(
    `/api/projects/${projectId}/audit-events`,
  );
  return response.events;
}

export function getWorkflowEventsUrl(runId: string) {
  return `${API_BASE_URL}/api/workflows/${runId}/events`;
}

export function getMvpEval(projectId: string) {
  return apiFetch<MvpEval>(`/api/projects/${projectId}/evals/mvp`);
}

export function getV1ResearchEval(projectId: string) {
  return apiFetch<V1ResearchEval>(`/api/projects/${projectId}/evals/v1-research`);
}

export function getAIStatus() {
  return apiFetch<AIStatus>("/api/ai/status");
}
