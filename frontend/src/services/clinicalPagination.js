import api from './api';

export const CLINICAL_PAGE_SIZE = 50;
export const MAX_RETAINED_CLINICAL_RECORDS = 1000;
export const MAX_CLINICAL_PAGE = 1000;

let sessionGeneration = 0;
const inFlight = new Map();

export function cancelClinicalPageRequests() {
  sessionGeneration += 1;
  for (const request of inFlight.values()) request.controller.abort();
  inFlight.clear();
}

function sharedPageRequest(key, load) {
  const existing = inFlight.get(key);
  if (existing) return existing.promise;
  const controller = new AbortController();
  const generation = sessionGeneration;
  const checkCurrent = () => {
    if (controller.signal.aborted || generation !== sessionGeneration) {
      throw new Error('Clinical list request was cancelled');
    }
  };
  const promise = load(controller.signal, checkCurrent);
  const entry = { controller, promise };
  inFlight.set(key, entry);
  promise.then(
    () => { if (inFlight.get(key) === entry) inFlight.delete(key); },
    () => { if (inFlight.get(key) === entry) inFlight.delete(key); },
  );
  return promise;
}

function appendUnique(target, seen, pageItems, idField = 'id', otherCount = 0) {
  for (const item of pageItems) {
    const id = item && typeof item === 'object' ? item[idField] : undefined;
    if (id != null && seen.has(id)) continue;
    if (target.length + otherCount >= MAX_RETAINED_CLINICAL_RECORDS) {
      throw new Error('Too many clinical records to display safely');
    }
    if (id != null) seen.add(id);
    target.push(item);
  }
}

// One-page replacement for screens with explicit navigation. No prior page is
// retained by this helper; the caller keys its UI query by page and identity.
export function fetchClinicalPage(path, page = 1, idField = 'id') {
  if (!Number.isInteger(page) || page < 1 || page > MAX_CLINICAL_PAGE) {
    return Promise.reject(new Error('Clinical page is invalid'));
  }
  return sharedPageRequest(`page:${path}:${page}:${idField}`, async (signal, checkCurrent) => {
    const response = await api.get(path, {
      params: { page, page_size: CLINICAL_PAGE_SIZE }, signal,
    });
    checkCurrent();
    if (!Array.isArray(response.data) || response.data.length > CLINICAL_PAGE_SIZE) {
      throw new Error('Clinical list response is invalid');
    }
    const data = [];
    appendUnique(data, new Set(), response.data, idField);
    return { data, page, hasNext: response.data.length === CLINICAL_PAGE_SIZE };
  });
}

// Keep the existing array contract while bounding retained records and sharing
// concurrent requests for the same authorized route.
export function fetchClinicalPages(path, { untilEmpty = false } = {}) {
  return sharedPageRequest(`list:${path}:${untilEmpty}`, async (signal, checkCurrent) => {
    const items = [];
    const seen = new Set();
    for (let page = 1; page <= MAX_CLINICAL_PAGE; page += 1) {
      const response = await api.get(path, {
        params: { page, page_size: CLINICAL_PAGE_SIZE }, signal,
      });
      checkCurrent();
      if (!Array.isArray(response.data) || response.data.length > CLINICAL_PAGE_SIZE) {
        throw new Error('Clinical list response is invalid');
      }
      appendUnique(items, seen, response.data);
      if (response.data.length === 0 || (!untilEmpty && response.data.length < CLINICAL_PAGE_SIZE)) {
        return { data: items };
      }
    }
    throw new Error('Clinical list exceeds the supported page range');
  });
}

// Patient-history routes page their appointment and released-report arrays together.
export function fetchClinicalHistoryPages(path) {
  return sharedPageRequest(`history:${path}`, async (signal, checkCurrent) => {
    let first;
    const appointments = [];
    const reports = [];
    const seenAppointments = new Set();
    const seenReports = new Set();
    for (let page = 1; page <= MAX_CLINICAL_PAGE; page += 1) {
      const response = await api.get(path, {
        params: { page, page_size: CLINICAL_PAGE_SIZE }, signal,
      });
      checkCurrent();
      const data = response.data;
      if (!data || !Array.isArray(data.appointments) || !Array.isArray(data.reports)
        || data.appointments.length > CLINICAL_PAGE_SIZE || data.reports.length > CLINICAL_PAGE_SIZE) {
        throw new Error('Clinical history response is invalid');
      }
      first ??= data;
      appendUnique(appointments, seenAppointments, data.appointments, 'id', reports.length);
      appendUnique(reports, seenReports, data.reports, 'request_id', appointments.length);
      if (data.appointments.length < CLINICAL_PAGE_SIZE && data.reports.length < CLINICAL_PAGE_SIZE) {
        return { data: { ...first, appointments, reports } };
      }
    }
    throw new Error('Clinical history exceeds the supported page range');
  });
}
