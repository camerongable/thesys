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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = `Request failed with ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      message = body.detail ?? message;
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
