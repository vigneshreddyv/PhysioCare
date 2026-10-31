import React from 'react';

const FLOW_ID_KEY = 'current_laboratory_flow_id';
const STATE_PREFIX = 'laboratory_booking_';
const STALE_MS = 24 * 60 * 60 * 1000; // 24 hours

/**
 * Generates a simple flow ID using timestamp and random string.
 * Not cryptographically secure but sufficient for avoiding collisions in the same browser.
 */
const generateFlowId = () => {
  return Date.now() + '-' + Math.random().toString(36).substring(2, 9);
};

/**
 * Gets the current flow ID from sessionStorage, generating and storing one if none exists.
 * @returns {string} The flow ID for the current tab.
 */
export const getFlowId = () => {
  let flowId = sessionStorage.getItem(FLOW_ID_KEY);
  if (!flowId) {
    flowId = generateFlowId();
    sessionStorage.setItem(FLOW_ID_KEY, flowId);
  }
  return flowId;
};

/**
 * Gets the laboratory booking state for the current flow ID from localStorage.
 * Returns null if no state exists, state is stale, or data is corrupted.
 * @returns {Object|null} The state object or null.
 */
export const getState = () => {
  const flowId = getFlowId();
  if (!flowId) return null;

  const stateStr = localStorage.getItem(STATE_PREFIX + flowId);
  if (!stateStr) return null;

  try {
    const state = JSON.parse(stateStr);
    // Validate state has a timestamp and is not stale
    if (state.timestamp && (Date.now() - state.timestamp) > STALE_MS) {
      // Stale state, treat as nonexistent
      return null;
    }
    // Basic validation: state should be an object
    if (typeof state !== 'object' || state === null) return null;
    return state;
  } catch (error) {
    // Corrupted JSON
    console.warn('Failed to parse laboratory booking state:', error);
    return null;
  }
};

/**
 * Merges partialState into the current state for the flow ID and saves to localStorage.
 * @param {Object} partialState - The partial state to merge.
 */
export const setState = (partialState) => {
  const flowId = getFlowId();
  if (!flowId) return;

  // Get current state or initialize with default timestamp
  let state = getState();
  if (!state) {
    state = { timestamp: Date.now() };
  } else {
    // Ensure timestamp exists
    if (!state.timestamp) state.timestamp = Date.now();
  }

  // Merge partial state
  Object.assign(state, partialState);
  // Update timestamp
  state.timestamp = Date.now();

  // Save to localStorage
  try {
    localStorage.setItem(STATE_PREFIX + flowId, JSON.stringify(state));
  } catch (e) {
    console.warn('Failed to save laboratory booking state:', e);
  }
};

/**
 * Clears the laboratory booking state for the current flow ID from localStorage
 * and removes the flow ID from sessionStorage.
 */
export const clearState = () => {
  const flowId = sessionStorage.getItem(FLOW_ID_KEY);
  if (flowId) {
    localStorage.removeItem(STATE_PREFIX + flowId);
    sessionStorage.removeItem(FLOW_ID_KEY);
  }
};

