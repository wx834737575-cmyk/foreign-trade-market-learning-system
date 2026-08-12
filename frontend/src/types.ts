export type Tone = "positive" | "warning" | "negative" | "neutral";

export interface EnvironmentCard {
  name: string;
  status: string;
  tone: Tone;
  summary: string;
}

export interface Indicator {
  code: string;
  name: string;
  value: number;
  unit: string;
  period: string;
  publishedAt: string | null;
  qualityStatus: string;
  source: { name: string; url: string };
  note: string | null;
}

export interface DashboardData {
  asOf: string;
  demoMode: boolean;
  dataStatus: string;
  environment: EnvironmentCard[];
  indicators: Indicator[];
  derived: { m1M2Gap: number | null; gapUnit: string };
  trends: Record<string, Array<{ period: string; value: number; qualityStatus: string }>>;
}

export interface SourceItem {
  code: string;
  name: string;
  url: string;
  authorityLevel: string;
  acquisitionMode: string;
  notes?: string;
  evidence: null | { sha256: string; qualityStatus: string; fetchedAt: string; parserVersion: string | null };
}

export interface NoteItem {
  id: number;
  period: string;
  title: string;
  content: string;
  confidence: string;
  outcome: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface UpdateResult {
  checkedAt: string;
  results: Array<{ sourceCode: string; status: string; message: string }>;
}

export interface CalendarItem {
  datasetCode: string;
  period: string;
  expectedFrom: string | null;
  expectedTo: string | null;
  status: string;
  actualReleaseAt: string | null;
}

export interface ChannelItem {
  code: string;
  name: string;
  type: string;
  status: string;
  plannedLaunch: string | null;
  notes: string | null;
}
