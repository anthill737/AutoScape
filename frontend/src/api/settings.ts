import { parseApiError } from "./errors";

export const SETTINGS_KEYS = [
  {
    name: "GOOGLE_API_KEY",
    signupUrl: "https://aistudio.google.com/app/apikey",
  },
  {
    name: "OPENAI_API_KEY",
    signupUrl: "https://platform.openai.com/api-keys",
  },
  {
    name: "ANTHROPIC_API_KEY",
    signupUrl: "https://console.anthropic.com/settings/keys",
  },
  {
    name: "PERPLEXITY_API_KEY",
    signupUrl: "https://www.perplexity.ai/settings/api",
  },
] as const;

export type SettingsKeyName = (typeof SETTINGS_KEYS)[number]["name"];

export interface SettingsKeyStatus {
  name: SettingsKeyName;
  set: boolean;
  masked_value: string | null;
}

export interface SettingsKeyTestResult {
  ok: boolean;
  error?: string;
}

export async function listSettingsKeys(): Promise<SettingsKeyStatus[]> {
  const res = await fetch("/api/settings/keys");
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to fetch settings: ${res.status}`));
  }
  return res.json() as Promise<SettingsKeyStatus[]>;
}

export async function saveSettingsKey(
  name: SettingsKeyName,
  value: string,
): Promise<SettingsKeyStatus> {
  const res = await fetch(`/api/settings/keys/${name}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value }),
  });
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to save ${name}: ${res.status}`));
  }
  return res.json() as Promise<SettingsKeyStatus>;
}

export async function clearSettingsKey(
  name: SettingsKeyName,
): Promise<SettingsKeyStatus> {
  const res = await fetch(`/api/settings/keys/${name}`, { method: "DELETE" });
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to clear ${name}: ${res.status}`));
  }
  return res.json() as Promise<SettingsKeyStatus>;
}

export async function testSettingsKey(
  name: SettingsKeyName,
): Promise<SettingsKeyTestResult> {
  const res = await fetch(`/api/settings/keys/${name}/test`, { method: "POST" });
  if (!res.ok) {
    throw new Error(await parseApiError(res, `Failed to test ${name}: ${res.status}`));
  }
  return res.json() as Promise<SettingsKeyTestResult>;
}
