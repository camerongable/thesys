export type ProjectStatus = "active" | "paused" | "killed" | "launched" | "archived";

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
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  steps: WorkflowStep[];
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

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown; message?: unknown };
      message = formatApiError(body, message);
    } catch {
      // Preserve the status-based fallback when the response is not JSON.
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
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

export function getWorkflowEventsUrl(runId: string) {
  return `${API_BASE_URL}/api/workflows/${runId}/events`;
}

export function getMvpEval(projectId: string) {
  return apiFetch<MvpEval>(`/api/projects/${projectId}/evals/mvp`);
}

export function getAIStatus() {
  return apiFetch<AIStatus>("/api/ai/status");
}
