/**
 * API client for Red Flag Master Tracker, Action Modal, and Attachments
 */

export interface RedFlagFilters {
  search?: string;
  status?: string;
  targetDepartment?: string;
  raisedByDepartment?: string;
  category5M?: string;
  severity?: string;
  plant?: string;
  raisedFrom?: string;
  raisedTo?: string;
  ordering?: string;
  page?: number;
  pageSize?: number;
  slaBreached?: boolean;
}

export interface RedFlagListItem {
  id: number;
  srNo: number;
  version: number;
  rfNo: string;
  raisedAt: string;
  targetDate: string | null;
  raisedByName: string;
  raisedByRole: string;
  raisedByDepartmentCode: string;
  raisedByDepartmentName: string;
  targetDepartmentCode: string;
  targetDepartmentName: string;
  targetPerson: string;
  teamLeader: string;
  closureResponsibility: string;
  plantCode: string;
  lineName: string;
  stationName: string;
  modelName: string;
  redFlagType: string;
  redFlagSubtype: string;
  category5M: string;
  severity: string;
  description: string;
  containmentAction: string;
  qtyQuarantined: number;
  containmentStatus: string;
  status: string;
  qaCustodianName: string | null;
  qaCustodianStatus: string;
  sustenanceStartDate: string | null;
  sustenanceAchieved: boolean;
  thumbnailUrl: string | null;
  containmentSlaMinutes: number | null;
  containmentSlaBreached: boolean;
}

export interface RedFlagListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: RedFlagListItem[];
}

export interface RedFlagsSummary {
  totalRaised: number;
  openActionNeeded: number;
  containedCount: number;
  underSustenance: number;
  closedSustained: number;
  qaCustodianBacklog: number;
}

export interface RedFlagDetail extends RedFlagListItem {
  targetDepartmentId?: number;
  qaCustodianId?: number | null;
  qaCustodianNotes?: string;
  plantId?: number;
  repetitiveOccurrence?: boolean;
  containment?: {
    id: number;
    status: string;
    qtyQuarantined: number;
    action: string;
    redTagNo: string;
    verifiedBy: number | null;
    verifiedByName: string | null;
    verifiedAt: string | null;
    containedAt: string | null;
    verificationNote: string;
  };
  attachments?: Array<{
    id: number;
    kind: string;
    status: string;
    isCurrent: boolean;
    url: string | null;
    thumbnailUrl: string | null;
    uploadedByName: string;
    createdAt: string;
  }>;
  statusHistory?: Array<{
    id: number;
    fromStatus: string;
    toStatus: string;
    changedByName: string | null;
    changedAt: string;
    reason: string;
  }>;
  fieldChanges?: Array<{
    id: number;
    fieldName: string;
    oldValue: string;
    newValue: string;
    changedByName: string | null;
    changedAt: string;
  }>;
}

// Token management
export function getAccessToken(): string | null {
  return localStorage.getItem('access_token') || localStorage.getItem('token');
}

export function setAccessToken(token: string) {
  localStorage.setItem('access_token', token);
}

/**
 * Ensures a valid JWT token exists; logs in as default demo user if needed
 */
export async function ensureAuthToken(): Promise<string> {
  const existing = getAccessToken();
  if (existing) return existing;

  try {
    const res = await fetch('/api/auth/token/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: 'qacustodian',
        password: 'demo12345',
      }),
    });
    if (res.ok) {
      const data = await res.json();
      if (data.access) {
        setAccessToken(data.access);
        return data.access;
      }
    }
  } catch (err) {
    console.error('Failed to obtain auth token:', err);
  }
  return '';
}

async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  let token = await ensureAuthToken();
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  let response = await fetch(url, { ...options, headers });

  if (response.status === 401) {
    // Retry once with refreshed or freshly obtained token
    localStorage.removeItem('access_token');
    token = await ensureAuthToken();
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
      response = await fetch(url, { ...options, headers });
    }
  }

  return response;
}

function buildQueryString(params: Record<string, any>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '' && value !== 'All') {
      // Map frontend param names to backend snake_case if needed
      let paramKey = key;
      if (key === 'targetDepartment') paramKey = 'target_department';
      else if (key === 'raisedByDepartment') paramKey = 'raised_by_department';
      else if (key === 'category5M') paramKey = 'category_5m';
      else if (key === 'raisedFrom') paramKey = 'raised_from';
      else if (key === 'raisedTo') paramKey = 'raised_to';
      else if (key === 'pageSize') paramKey = 'page_size';
      else if (key === 'slaBreached') paramKey = 'sla_breached';

      query.append(paramKey, String(value));
    }
  }
  const str = query.toString();
  return str ? `?${str}` : '';
}

// -------------------------------------------------------------
// Tracker Endpoints (Phase 3)
// -------------------------------------------------------------

export async function fetchRedFlags(filters: RedFlagFilters = {}): Promise<RedFlagListResponse> {
  const qs = buildQueryString(filters);
  const res = await authFetch(`/api/redflag/v1/flags/${qs}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch red flags: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchRedFlagsSummary(
  scoped = false,
  filters: RedFlagFilters = {}
): Promise<RedFlagsSummary> {
  const params: Record<string, any> = { ...filters };
  if (scoped) {
    params.scoped = 'true';
  } else {
    delete params.scoped;
  }
  // remove pagination params from summary query
  delete params.page;
  delete params.pageSize;

  const qs = buildQueryString(params);
  const res = await authFetch(`/api/redflag/v1/flags/summary/${qs}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch flags summary: ${res.statusText}`);
  }
  return res.json();
}

export async function exportRedFlagsCsv(filters: RedFlagFilters = {}): Promise<void> {
  const exportParams = { ...filters };
  delete exportParams.page;
  delete exportParams.pageSize;

  const qs = buildQueryString(exportParams);
  const res = await authFetch(`/api/redflag/v1/flags/export.csv${qs}`);
  if (!res.ok) {
    throw new Error(`CSV export failed: ${res.statusText}`);
  }

  // Extract filename or fallback to timestamped default
  let filename = `SFC_RedFlags_Master_${new Date().toISOString().slice(0, 10)}.csv`;
  const disposition = res.headers.get('content-disposition');
  if (disposition && disposition.includes('filename=')) {
    const match = disposition.match(/filename="?([^";]+)"?/);
    if (match && match[1]) filename = match[1];
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

// -------------------------------------------------------------
// Action Modal Endpoints (Phase 4)
// -------------------------------------------------------------

export async function fetchRedFlagDetail(id: number | string): Promise<RedFlagDetail> {
  const res = await authFetch(`/api/redflag/v1/flags/${id}/`);
  if (!res.ok) {
    throw new Error(`Failed to load flag #${id}: ${res.statusText}`);
  }
  return res.json();
}

export async function updateRedFlagDetails(
  id: number | string,
  payload: {
    version: number;
    targetDepartment?: string;
    targetPerson?: string;
    qaCustodianNotes?: string;
    redFlagType?: string;
    redFlagSubtype?: string;
    category5M?: string;
    severity?: string;
    description?: string;
    targetDate?: string;
    closureResponsibility?: string;
    teamLeader?: string;
    evidenceBeforeId?: number;
    [key: string]: any;
  }
): Promise<RedFlagDetail> {
  const res = await authFetch(`/api/redflag/v1/flags/${id}/details/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (res.status === 409) {
    const errorData = await res.json().catch(() => ({}));
    const err = new Error(errorData.error || 'Conflict: This flag was modified by another user.');
    (err as any).status = 409;
    (err as any).currentVersion = errorData.currentVersion;
    throw err;
  }

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || errData.error || `Update failed: ${res.status}`);
  }

  return res.json();
}

export async function updateRedFlagContainment(
  id: number | string,
  payload: {
    version: number;
    qtyQuarantined?: number;
    action?: string;
    redTagNo?: string;
    [key: string]: any;
  }
): Promise<RedFlagDetail> {
  const res = await authFetch(`/api/redflag/v1/flags/${id}/containment/`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (res.status === 409) {
    const errorData = await res.json().catch(() => ({}));
    const err = new Error(errorData.error || 'Conflict: This flag was modified by another user.');
    (err as any).status = 409;
    (err as any).currentVersion = errorData.currentVersion;
    throw err;
  }

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || errData.error || `Containment update failed: ${res.status}`);
  }

  return res.json();
}

export async function verifyContainment(
  id: number | string,
  verificationNote?: string
): Promise<RedFlagDetail> {
  const res = await authFetch(`/api/redflag/v1/flags/${id}/containment/verify/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ verificationNote: verificationNote || '' }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.error || errData.detail || `Verification failed: ${res.status}`);
  }

  return res.json();
}

export async function unverifyContainment(
  id: number | string,
  reason: string
): Promise<RedFlagDetail> {
  const res = await authFetch(`/api/redflag/v1/flags/${id}/containment/unverify/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.error || errData.detail || `Unverify failed: ${res.status}`);
  }

  return res.json();
}

export async function fetchRedFlagHistory(id: number | string): Promise<{
  redFlagId: number;
  rfNo: string;
  timeline: Array<{
    type: 'status_change' | 'field_change';
    timestamp: string;
    changedByName: string;
    [key: string]: any;
  }>;
}> {
  const res = await authFetch(`/api/redflag/v1/flags/${id}/history/`);
  if (!res.ok) {
    throw new Error(`Failed to load history: ${res.statusText}`);
  }
  return res.json();
}

// -------------------------------------------------------------
// Phase 2 Attachment Direct MinIO Upload & Confirm
// -------------------------------------------------------------

export function dataUrlToFile(dataUrl: string, filename: string): File {
  const arr = dataUrl.split(',');
  const mimeMatch = arr[0].match(/:(.*?);/);
  const mime = mimeMatch ? mimeMatch[1] : 'image/jpeg';
  const bstr = atob(arr[1]);
  let n = bstr.length;
  const u8arr = new Uint8Array(n);
  while (n--) {
    u8arr[n] = bstr.charCodeAt(n);
  }
  return new File([u8arr], filename, { type: mime });
}

export async function uploadAttachmentFile(
  file: File,
  kind: 'EVIDENCE_BEFORE' | 'CONTAINMENT_AFTER' | 'OTHER'
): Promise<{ id: number; url: string | null; thumbnailUrl: string | null }> {
  // 1. Request presigned upload
  const presignRes = await authFetch('/api/redflag/v1/attachments/presign/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      kind,
      filename: file.name,
      contentType: file.type || 'image/jpeg',
      size: file.size,
    }),
  });

  if (!presignRes.ok) {
    const errData = await presignRes.json().catch(() => ({}));
    throw new Error(errData.detail || errData.error || `Presign failed: ${presignRes.status}`);
  }

  const presignData = await presignRes.json();
  const attachmentId = presignData.attachmentId || presignData.attachment_id;
  const presignedPost = presignData.presignedPost || presignData.presigned_post;

  // 2. Direct upload to MinIO via S3 presigned POST
  if (presignedPost?.url) {
    const formData = new FormData();
    if (presignedPost.fields) {
      for (const [key, val] of Object.entries(presignedPost.fields)) {
        formData.append(key, val as string);
      }
    }
    formData.append('file', file);

    const s3Res = await fetch(presignedPost.url, {
      method: 'POST',
      body: formData,
    });

    if (!s3Res.ok && s3Res.status !== 204 && s3Res.status !== 200) {
      throw new Error(`MinIO S3 upload failed with status ${s3Res.status}`);
    }
  }

  // 3. Confirm upload with backend (sniff bytes and generate ~400px thumbnail)
  const confirmRes = await authFetch(`/api/redflag/v1/attachments/${attachmentId}/confirm/`, {
    method: 'POST',
  });

  if (!confirmRes.ok) {
    const errData = await confirmRes.json().catch(() => ({}));
    throw new Error(errData.error || errData.detail || `Confirm failed: ${confirmRes.status}`);
  }

  const confirmData = await confirmRes.json();
  return {
    id: attachmentId,
    url: confirmData.attachment?.url || null,
    thumbnailUrl: confirmData.attachment?.thumbnailUrl || null,
  };
}

export interface RedFlagCreatePayload {
  targetDepartmentId?: number;
  targetDepartment?: string;
  targetPerson: string;
  teamLeader?: string;
  lineName: string;
  stationName: string;
  modelName: string;
  plantId?: number;
  plant?: string;
  redFlagType?: string;
  redFlagSubtype?: string;
  severity?: string;
  category5M?: string;
  repetitiveOccurrence?: boolean;
  description: string;
  qtyQuarantined?: number;
  suspectQtyQuarantined?: number;
  containmentAction?: string;
  redTagNo?: string;
  evidenceBeforeId: number;
  containmentAfterId?: number | null;
  targetDate?: string;
}

export async function createRedFlag(payload: RedFlagCreatePayload): Promise<RedFlagDetail> {
  const res = await authFetch('/api/redflag/v1/flags/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || errData.error || JSON.stringify(errData) || `Create failed: ${res.status}`);
  }

  return res.json();
}

