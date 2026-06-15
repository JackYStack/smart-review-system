export type ParseTask = {
  document_id: string;
  file_name: string;
  file_type: string;
  status: string;
  scenario?: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export async function submitParseTask(file: File, scenario: string): Promise<ParseTask> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/api/v1/parse?scenario=${encodeURIComponent(scenario)}`, {
    method: "POST",
    body: formData
  });

  if (!response.ok) {
    throw new Error("parse task failed");
  }

  return response.json() as Promise<ParseTask>;
}
