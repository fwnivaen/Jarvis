/**
 * Declaration-only boundary for upstream services absent from this repository.
 *
 * This file supplies no runtime objects, endpoint URLs, demo data, permission
 * grants, schedules, or executors. Current workspace surfaces must remain in a
 * connection-required state until a real adapter is supplied and verified.
 *
 * Replace each `unknown` payload with the upstream module's actual type when
 * wiring it. `unknown` is intentional: this UI must not invent a domain schema.
 * No frontend build step or TypeScript runtime is required by these declarations.
 */

export type MissingServiceName =
  | 'agency'
  | 'studio'
  | 'agents'
  | 'trading'
  | 'automations'
  | 'workspace'
  | 'vaultCrypto'
  | 'computerControl';

/** Unavailable is distinct from a connected service returning no records. */
export interface NeedsWiring<Name extends MissingServiceName> {
  readonly status: 'needs-wiring';
  readonly service: Name;
  readonly reason: string;
  /** The real module/contract must be supplied; do not invent a filesystem path. */
  readonly required: 'upstream-module-and-contract';
}

export interface ServiceFailure {
  readonly status: 'error';
  readonly message: string;
  readonly retryable: boolean;
}

export interface ServiceUnavailable {
  readonly status: 'unavailable';
  readonly reason: string;
}

/** State came from a connected upstream read, not placeholder UI defaults. */
export interface ServiceState<State> {
  readonly status: 'ready';
  readonly value: State;
}

export type ReadResult<State> =
  | ServiceState<State>
  | ServiceUnavailable
  | ServiceFailure;

export interface RequestOptions {
  readonly signal?: AbortSignal;
}

/** An upstream-specific permission or approval receipt; not a client boolean. */
export interface AuthorityReceipt<Receipt> {
  readonly source: 'explicit-approval' | 'scoped-standing-permission';
  readonly receipt: Receipt;
}

/** A proposed action is reviewable before it can be submitted for execution. */
export interface ActionProposal<Action, Proposal> {
  readonly status: 'awaiting-approval';
  readonly action: Action;
  readonly summary: string;
  readonly proposal: Proposal;
}

export interface ExecutionProgress<Progress> {
  readonly status: 'executing';
  /** Null means the upstream has no numeric progress; never simulate percent. */
  readonly fraction: number | null;
  readonly detail: Progress;
}

/** Completion and verification are separate facts at this boundary. */
export interface UnverifiedCompletion<Result> {
  readonly status: 'completed-unverified';
  readonly result: Result;
  readonly reason: string;
}

export interface VerifiedCompletion<Result, Evidence> {
  readonly status: 'verified';
  readonly result: Result;
  /** Upstream readback/receipt evidence using the upstream's actual contract. */
  readonly evidence: Evidence;
}

export interface CancelledExecution {
  readonly status: 'cancelled';
}

export type ExecutionEvent<Progress, Result, Evidence> =
  | ExecutionProgress<Progress>
  | UnverifiedCompletion<Result>
  | VerifiedCompletion<Result, Evidence>
  | CancelledExecution
  | ServiceUnavailable
  | ServiceFailure;

/**
 * Proposed adapter interface, not an assertion that an upstream has these APIs.
 * The implementation must map its real authorization, cancellation, and result
 * verification contracts. No action methods exist on a NeedsWiring value.
 */
export interface ConnectedService<
  Name extends MissingServiceName,
  State,
  Action,
  Proposal,
  Receipt,
  Progress,
  Result,
  Evidence,
> {
  readonly status: 'connected';
  readonly service: Name;
  read(options?: RequestOptions): Promise<ReadResult<State>>;
  prepare(
    action: Action,
    options?: RequestOptions,
  ): Promise<ActionProposal<Action, Proposal> | ServiceUnavailable | ServiceFailure>;
  execute(
    proposal: Proposal,
    authority: AuthorityReceipt<Receipt>,
    options?: RequestOptions,
  ): AsyncIterable<ExecutionEvent<Progress, Result, Evidence>>;
}

/**
 * Domain slots intentionally have no guessed fields (orders, balances, jobs,
 * tenant IDs, encryption keys, etc.). Supply concrete upstream types at wiring.
 */
export interface UpstreamTypes {
  readonly state: unknown;
  readonly action: unknown;
  readonly proposal: unknown;
  readonly authority: unknown;
  readonly progress: unknown;
  readonly result: unknown;
  readonly evidence: unknown;
}

export type ServiceConnection<
  Name extends MissingServiceName,
  Types extends UpstreamTypes,
> = NeedsWiring<Name> | ConnectedService<
  Name,
  Types['state'],
  Types['action'],
  Types['proposal'],
  Types['authority'],
  Types['progress'],
  Types['result'],
  Types['evidence']
>;

/** A registry of future contracts, not an exported runtime service registry. */
export interface UpstreamTypeMap {
  readonly agency: UpstreamTypes;
  readonly studio: UpstreamTypes;
  readonly agents: UpstreamTypes;
  readonly trading: UpstreamTypes;
  readonly automations: UpstreamTypes;
  readonly workspace: UpstreamTypes;
  readonly vaultCrypto: UpstreamTypes;
  readonly computerControl: UpstreamTypes;
}

export type UpstreamAdapters<Types extends UpstreamTypeMap> = {
  readonly [Name in MissingServiceName]: ServiceConnection<Name, Types[Name]>;
};

/** The only accurate state for all missing upstream adapters in this checkout. */
export interface CurrentUnwiredServices {
  // TODO(sir): connect to Agency using its real service module and state/action/result contract.
  readonly agency: NeedsWiring<'agency'>;
  // TODO(sir): connect to Studio using its real project/content service contract.
  readonly studio: NeedsWiring<'studio'>;
  // TODO(sir): connect to agents using the real runner, lifecycle, approval, and cancellation contracts.
  readonly agents: NeedsWiring<'agents'>;
  // TODO(sir): connect to trading using the actual broker, authority, receipt, and reconciliation contracts.
  readonly trading: NeedsWiring<'trading'>;
  // TODO(sir): connect to automations using the actual scheduler, timezone, stored-run, and cancellation contracts.
  readonly automations: NeedsWiring<'automations'>;
  // TODO(sir): connect to workspace using actual identity, membership, authorization, storage, and sync contracts.
  readonly workspace: NeedsWiring<'workspace'>;
  // TODO(sir): connect to Vault crypto through its real encryption/key-management boundary; never expose raw secret keys in browser state.
  readonly vaultCrypto: NeedsWiring<'vaultCrypto'>;
  // TODO(sir): connect to computer control using the real executor, permission bridge, cancellation, and observable verification contracts.
  readonly computerControl: NeedsWiring<'computerControl'>;
}
