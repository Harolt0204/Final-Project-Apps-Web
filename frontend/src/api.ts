// Thin client for the FastAPI backend. Types mirror the Pydantic schemas.

export type UserRole = "admin" | "professor" | "student";

export type ThesisStatus =
  | "PROPOSED"
  | "TOPIC_APPROVED"
  | "THESIS_I"
  | "THESIS_II"
  | "IN_REVIEW"
  | "READY_FOR_DEFENSE"
  | "DEFENDED"
  | "REJECTED";

export interface User {
  user_id: number;
  email: string;
  role: UserRole;
  display_name: string;
  student_id: number | null;
  professor_id: number | null;
  is_active: boolean;
  last_login_at: string | null;
}

interface Person {
  full_name: string;
  email: string;
}

export interface School {
  school_id: number;
  code: string;
  name: string;
}

export interface Period {
  period_id: number;
  name: string;
  start_date: string | null;
  end_date: string | null;
}

export interface PersonRecord extends Person {
  national_id: string | null;
  first_name: string;
  last_name: string;
  institution: string | null;
  school: School | null;
  has_account: boolean;
}

export interface Student extends PersonRecord {
  student_id: number;
  phone: string | null;
  has_thesis: boolean;
}

export interface Professor extends PersonRecord {
  professor_id: number;
}

export type PersonKind = "students" | "professors";

export interface PersonInput {
  national_id?: string | null;
  first_name?: string;
  last_name?: string;
  email?: string;
  school_id?: number | null;
  institution?: string | null;
  phone?: string | null;
  account_password?: string;
}

export interface ThesisSummary {
  thesis_id: number;
  title: string;
  status: ThesisStatus;
  student: Person & { student_id: number; school: School | null };
  tutors: { role: "Tutor" | "Co-Tutor"; professor: Person & { professor_id: number } }[];
  reviewers: {
    role: "President" | "Committee";
    professor: Person & { professor_id: number };
    approved_at: string | null;
    grade: string | null;
  }[];
  my_roles: string[];
  updated_at: string;
}

export interface Room {
  room_id: number;
  name: string;
  building: string;
  capacity: number | null;
  is_active: boolean;
  label: string;
}

export interface Defense {
  defense_id: number;
  scheduled_at: string;
  ends_at: string;
  duration_minutes: number;
  modality: "In-person" | "Virtual";
  room: Room | null;
  meeting_url: string | null;
  final_grade: string | null;
  grades_recorded: number;
  min_passing_grade: string | null;
  passed: boolean | null;
}

export interface CalendarItem extends Defense {
  thesis_id: number;
  thesis_title: string;
  student_name: string;
  jury: string[];
}

export interface DefenseInput {
  scheduled_at: string;
  duration_minutes: number;
  modality: "In-person" | "Virtual";
  room_id?: number;
  meeting_url?: string;
}

export interface ThesisDetail extends ThesisSummary {
  defense: Defense | null;
  abstract: string | null;
  periods: Period[];
  status_history: {
    from_status: ThesisStatus | null;
    to_status: ThesisStatus;
    changed_at: string;
    changed_by_name: string;
    comment: string | null;
  }[];
  created_at: string;
}

export interface WorkflowOption {
  to_status: ThesisStatus;
  label: string;
  actors: string[];
  blockers: string[];
  comment_required: boolean;
  can_perform: boolean;
}

export type ObservationStatus = "OPEN" | "ADDRESSED" | "RESOLVED";

export interface Observation {
  observation_id: number;
  professor_id: number;
  author_name: string;
  text: string;
  status: ObservationStatus;
  response: string | null;
  responded_at: string | null;
  resolved_at: string | null;
  created_at: string;
}

export interface SimilarityCheck {
  check_id: number;
  similarity_percentage: string;
  checked_at: string;
  tool: string;
  threshold_applied: string;
  verdict: "ACCEPTED" | "REJECTED";
  report_url: string | null;
  notes: string | null;
  recorded_by_name: string | null;
}

export interface RequirementType {
  requirement_type_id: number;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  sort_order: number;
}

export type RequirementState = "PENDING" | "CERTIFIED" | "REJECTED";

export interface RequirementItem {
  requirement_type: RequirementType;
  status: RequirementState;
  certified_at: string | null;
  certified_by_name: string | null;
  evidence_url: string | null;
  notes: string | null;
}

export interface StudentRequirements {
  student_id: number;
  student_name: string;
  complete: boolean;
  items: RequirementItem[];
}

export interface Setting {
  setting_key: string;
  value: string;
  description: string | null;
}

// Reports (Sprint 6)
export interface Overview {
  total_theses: number;
  active_theses: number;
  by_status: Record<ThesisStatus, number>;
  upcoming_defenses_30_days: number;
}

export interface WorkloadRow {
  professor_id: number;
  full_name: string;
  school: string | null;
  tutor_active: number;
  cotutor_active: number;
  president_active: number;
  committee_active: number;
  total_active: number;
  supervised_defended: number;
}

export interface SchoolGrades {
  school_code: string;
  school_name: string;
  defenses: number;
  average_grade: string;
  min_grade: string;
  max_grade: string;
  passed: number;
  pass_rate: string;
}

export interface RoomAvailability {
  date_from: string;
  days: number;
  working_hours: string;
  rooms: {
    room_id: number;
    label: string;
    capacity: number | null;
    occupancy: string;
    days: {
      day: string;
      bookings: { thesis_id: number; thesis_title: string; start: string; end: string }[];
      free: { start: string; end: string }[];
      occupancy: string;
    }[];
  }[];
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

// sessionStorage: the token disappears when the tab is closed. It is still readable by
// scripts on this origin, so the app never injects untrusted HTML (React escapes text).
const TOKEN_KEY = "tm_token";

export const tokenStore = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

let onUnauthorized: () => void = () => {};
export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = tokenStore.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(path, { ...init, headers });
  if (response.status === 401 && token) onUnauthorized();
  if (response.status === 204) return undefined as T;
  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; user: User }>("/api/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    }),
  me: () => request<User>("/api/auth/me"),
  theses: () => request<ThesisSummary[]>("/api/theses"),
  thesis: (id: number) => request<ThesisDetail>(`/api/theses/${id}`),
  users: () => request<User[]>("/api/users"),
  createUser: (data: {
    email: string;
    password: string;
    role: UserRole;
    student_id?: number;
    professor_id?: number;
  }) => request<User>("/api/users", json("POST", data)),
  updateUser: (id: number, data: { is_active?: boolean; password?: string }) =>
    request<User>(`/api/users/${id}`, json("PATCH", data)),

  // Theses (Sprint 2)
  registerThesis: (data: { title: string; abstract?: string | null; student_id?: number; period_ids?: number[] }) =>
    request<ThesisDetail>("/api/theses", json("POST", data)),
  updateThesis: (id: number, data: { title?: string; abstract?: string | null; period_ids?: number[] }) =>
    request<ThesisDetail>(`/api/theses/${id}`, json("PATCH", data)),
  assignTutor: (id: number, slot: "tutor" | "co-tutor", professor_id: number) =>
    request<ThesisDetail>(`/api/theses/${id}/tutors/${slot}`, json("PUT", { professor_id })),
  removeTutor: (id: number, slot: "tutor" | "co-tutor") =>
    request<ThesisDetail>(`/api/theses/${id}/tutors/${slot}`, { method: "DELETE" }),

  // Workflow and review (Sprint 3)
  workflow: (id: number) => request<{ status: ThesisStatus; options: WorkflowOption[] }>(`/api/theses/${id}/workflow`),
  changeStatus: (id: number, to_status: ThesisStatus, comment?: string) =>
    request<ThesisDetail>(`/api/theses/${id}/status`, json("POST", { to_status, comment: comment || null })),
  setReviewer: (id: number, professorId: number, role: "President" | "Committee") =>
    request<ThesisDetail>(`/api/theses/${id}/reviewers/${professorId}`, json("PUT", { role })),
  removeReviewer: (id: number, professorId: number) =>
    request<ThesisDetail>(`/api/theses/${id}/reviewers/${professorId}`, { method: "DELETE" }),
  setApproval: (id: number, approve: boolean) =>
    request<ThesisDetail>(`/api/theses/${id}/approval`, { method: approve ? "PUT" : "DELETE" }),
  observations: (id: number) => request<Observation[]>(`/api/theses/${id}/observations`),
  addObservation: (id: number, text: string) =>
    request<Observation>(`/api/theses/${id}/observations`, json("POST", { text })),
  respondObservation: (id: number, oid: number, response: string) =>
    request<Observation>(`/api/theses/${id}/observations/${oid}/response`, json("POST", { response })),
  resolveObservation: (id: number, oid: number, accept: boolean) =>
    request<Observation>(`/api/theses/${id}/observations/${oid}/${accept ? "resolve" : "reopen"}`, {
      method: "POST",
    }),

  // Similarity, requirements and settings (Sprint 4)
  similarity: (id: number) =>
    request<{ threshold: string; checks: SimilarityCheck[] }>(`/api/theses/${id}/similarity-checks`),
  addSimilarity: (
    id: number,
    data: { similarity_percentage: string; tool: string; checked_at?: string; report_url?: string; notes?: string },
  ) => request<SimilarityCheck>(`/api/theses/${id}/similarity-checks`, json("POST", data)),
  thesisRequirements: (id: number) => request<StudentRequirements>(`/api/theses/${id}/requirements`),
  studentRequirements: (studentId: number) =>
    request<StudentRequirements>(`/api/students/${studentId}/requirements`),
  setRequirement: (
    studentId: number,
    typeId: number,
    data: { status: "CERTIFIED" | "REJECTED"; evidence_url?: string; notes?: string },
  ) => request<StudentRequirements>(`/api/students/${studentId}/requirements/${typeId}`, json("PUT", data)),
  clearRequirement: (studentId: number, typeId: number) =>
    request<StudentRequirements>(`/api/students/${studentId}/requirements/${typeId}`, { method: "DELETE" }),
  requirementTypes: (includeInactive = false) =>
    request<RequirementType[]>(`/api/requirement-types?include_inactive=${includeInactive}`),
  createRequirementType: (data: { code: string; name: string; description?: string; sort_order?: number }) =>
    request<RequirementType>("/api/requirement-types", json("POST", data)),
  updateRequirementType: (id: number, data: Partial<Omit<RequirementType, "requirement_type_id" | "code">>) =>
    request<RequirementType>(`/api/requirement-types/${id}`, json("PATCH", data)),
  settings: () => request<Setting[]>("/api/settings"),
  updateSetting: (key: string, value: string) => request<Setting>(`/api/settings/${key}`, json("PUT", { value })),

  // Rooms and defenses (Sprint 5)
  rooms: (includeInactive = false) => request<Room[]>(`/api/rooms?include_inactive=${includeInactive}`),
  createRoom: (data: { name: string; building: string; capacity?: number | null }) =>
    request<Room>("/api/rooms", json("POST", data)),
  updateRoom: (id: number, data: Partial<Pick<Room, "name" | "building" | "capacity" | "is_active">>) =>
    request<Room>(`/api/rooms/${id}`, json("PATCH", data)),
  roomBookings: (id: number, day: string) =>
    request<{ thesis_id: number; starts_at: string; ends_at: string }[]>(`/api/rooms/${id}/bookings?day=${day}`),
  calendar: (dateFrom?: string, dateTo?: string) => {
    const params = new URLSearchParams();
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return request<CalendarItem[]>(`/api/defenses?${params}`);
  },
  scheduleDefense: (id: number, data: DefenseInput) =>
    request<ThesisDetail>(`/api/theses/${id}/defense`, json("PUT", data)),
  cancelDefense: (id: number) => request<ThesisDetail>(`/api/theses/${id}/defense`, { method: "DELETE" }),
  recordGrade: (id: number, grade: string) =>
    request<ThesisDetail>(`/api/theses/${id}/defense/grade`, json("PUT", { grade })),

  // Reports and account (Sprint 6)
  overview: () => request<Overview>("/api/reports/overview"),
  workload: (periodId?: number) =>
    request<WorkloadRow[]>(`/api/reports/tutor-workload${periodId ? `?period_id=${periodId}` : ""}`),
  gradesBySchool: (dateFrom?: string, dateTo?: string) => {
    const params = new URLSearchParams();
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return request<{ min_passing_grade: string; overall_average: string | null; schools: SchoolGrades[] }>(
      `/api/reports/grades-by-school?${params}`,
    );
  },
  roomAvailability: (dateFrom: string, days: number) =>
    request<RoomAvailability>(`/api/reports/room-availability?date_from=${dateFrom}&days=${days}`),
  changePassword: (current_password: string, new_password: string) =>
    request<{ access_token: string; user: User }>("/api/auth/password", json("PUT", { current_password, new_password })),

  // People and catalogs
  people: <T extends PersonRecord>(kind: PersonKind, q = "") =>
    request<T[]>(`/api/${kind}` + (q ? `?q=${encodeURIComponent(q)}` : "")),
  createPerson: (kind: PersonKind, data: PersonInput) => request<PersonRecord>(`/api/${kind}`, json("POST", data)),
  updatePerson: (kind: PersonKind, id: number, data: PersonInput) =>
    request<PersonRecord>(`/api/${kind}/${id}`, json("PATCH", data)),
  deletePerson: (kind: PersonKind, id: number) => request<void>(`/api/${kind}/${id}`, { method: "DELETE" }),
  schools: () => request<School[]>("/api/schools"),
  periods: () => request<Period[]>("/api/periods"),
  createPeriod: (data: { name: string; start_date: string; end_date: string }) =>
    request<Period>("/api/periods", json("POST", data)),
  updatePeriod: (id: number, data: { name?: string; start_date?: string; end_date?: string }) =>
    request<Period>(`/api/periods/${id}`, json("PATCH", data)),
  deletePeriod: (id: number) => request<void>(`/api/periods/${id}`, { method: "DELETE" }),
};

export const personId = (p: PersonRecord): number =>
  "student_id" in p ? (p as Student).student_id : (p as Professor).professor_id;

/** YYYY-MM-DD in the browser's time zone, `offsetDays` from today. */
export function localDate(offsetDays = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export const STATUS_FLOW: ThesisStatus[] = [
  "PROPOSED",
  "TOPIC_APPROVED",
  "THESIS_I",
  "THESIS_II",
  "IN_REVIEW",
  "READY_FOR_DEFENSE",
  "DEFENDED",
];

export const STATUS_LABEL: Record<ThesisStatus, string> = {
  PROPOSED: "Topic proposed",
  TOPIC_APPROVED: "Topic approved",
  THESIS_I: "Thesis I",
  THESIS_II: "Thesis II",
  IN_REVIEW: "Committee review",
  READY_FOR_DEFENSE: "Ready for defense",
  DEFENDED: "Defended",
  REJECTED: "Rejected",
};
