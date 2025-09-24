/**
 * Workflow Node Type Definitions
 * Updated to support 4 core node types: entry, outcome, decision, general
 */

export enum WorkflowNodeType {
  ENTRY = 'entry',
  OUTCOME = 'outcome',
  DECISION = 'decision',
  GENERAL = 'general'
}

/**
 * Legacy node type mapping for migration
 */
export const LEGACY_NODE_TYPE_MAPPING: Record<string, WorkflowNodeType> = {
  'start': WorkflowNodeType.ENTRY,
  'end': WorkflowNodeType.OUTCOME,
  'action': WorkflowNodeType.GENERAL,
  'agent': WorkflowNodeType.GENERAL,
  'error': WorkflowNodeType.OUTCOME,
  'decision': WorkflowNodeType.DECISION
}

/**
 * Node metadata interface
 */
export interface WorkflowNodeMetadata {
  type: WorkflowNodeType
  agentType?: 'web' | 'voice' | 'custom'
  agentLabel?: string
  errorType?: 'timeout' | 'validation' | 'system' | 'business'
  prevType?: string // For tracking migrations
  [key: string]: any // Allow additional metadata
}

/**
 * Validation rules for workflow structure
 */
export const WORKFLOW_VALIDATION_RULES = {
  // At least one entry node is required
  requiresAtLeastOneEntry: true,
  
  // At least one outcome node is required
  requiresAtLeastOneOutcome: true,
  
  // Multiple entry nodes allowed (for multi-agent support)
  allowsMultipleEntries: true,
  
  // Multiple outcome nodes allowed (for different outcome types)
  allowsMultipleOutcomes: true,
  
  // Entry nodes cannot have incoming edges
  entryNodesHaveNoIncoming: true,
  
  // Outcome nodes cannot have outgoing edges
  outcomeNodesHaveNoOutgoing: true,
  
  // Decision nodes must have at least 2 outgoing edges
  decisionNodesRequireMultipleOutputs: true
}

/**
 * Helper function to migrate legacy node types
 */
export function migrateNodeType(legacyType: string): WorkflowNodeType {
  return LEGACY_NODE_TYPE_MAPPING[legacyType] || WorkflowNodeType.GENERAL
}

/**
 * Helper function to determine if a node is a terminal node
 */
export function isTerminalNode(nodeType: WorkflowNodeType): boolean {
  return nodeType === WorkflowNodeType.OUTCOME
}

/**
 * Helper function to determine if a node is an entry point
 */
export function isEntryNode(nodeType: WorkflowNodeType): boolean {
  return nodeType === WorkflowNodeType.ENTRY
}