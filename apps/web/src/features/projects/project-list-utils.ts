export type ProjectListFilterProject = {
  name: string;
  short_description?: string | null;
};

const disposableProjectPatterns = [
  /^\[demo\]/i,
  /\[[^\]]*\bqa\b[^\]]*\]/i,
  /\bdisposable\b/i,
  /\baudit\b/i,
  /\bendpoint\s+audit\b/i,
  /\bsprint\s+\d+.*\b(smoke|qa|test|browser)\b/i,
  /\bbrowser\s+(smoke|qa|test|check)\b/i,
  /\b(smoke|qa|browser)\s+test\b/i,
  /\btest\s+project\b/i,
  /\bbrowser\s+test\s+project\b/i,
  /\bdisposable\s+qa\b/i,
];

export function isDisposableProject(project: ProjectListFilterProject) {
  const name = project.name.trim();
  if (/^ai assistant for independent fitness coaches$/i.test(name)) {
    return false;
  }
  const searchableText = `${name} ${project.short_description ?? ""}`.trim();
  return disposableProjectPatterns.some((pattern) => pattern.test(searchableText));
}

export function filterHomepageProjects<T extends { project: ProjectListFilterProject }>(
  rows: T[],
  showTestProjects: boolean,
) {
  if (showTestProjects) {
    return rows;
  }
  return rows.filter((row) => !isDisposableProject(row.project));
}
