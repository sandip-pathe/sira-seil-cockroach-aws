"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ProofCandidateView, ProofWorkspaceView } from "@sira/api-client";
import {
  ArrowRight,
  Check,
  CircleAlert,
  Database,
  ExternalLink,
  Fingerprint,
  Play,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";

import { buyerDevelopmentHeaders, getBrowserApiClient } from "@/lib/api";

import styles from "./proof-workspace.module.css";

function compact(value: string) {
  return `${value.slice(0, 13)}…${value.slice(-9)}`;
}

function HashValue({ value }: { value: string }) {
  return (
    <code className={styles.hash} title={value}>
      {compact(value)}
    </code>
  );
}

function State({ children }: { children: React.ReactNode }) {
  return (
    <span className={styles.state}>
      <Check size={13} aria-hidden="true" />
      {children}
    </span>
  );
}

function Candidate({ candidate }: { candidate: ProofCandidateView }) {
  const passed = Object.values(candidate.gate_results).filter(Boolean).length;
  const total = Object.keys(candidate.gate_results).length;
  return (
    <article className={`${styles.candidate} ${candidate.selected ? styles.selected : ""}`}>
      <div className={styles.candidateHead}>
        <div>
          <span className={styles.eyebrow}>{candidate.seller_organization_id}</span>
          <h3>{candidate.adapter_id === "adapter-a" ? "ClearText Assist" : "Private Relay"}</h3>
        </div>
        {candidate.selected ? <span className={styles.winner}>Selected</span> : null}
      </div>
      <div className={styles.candidateScore}>
        <strong>
          {passed}/{total}
        </strong>
        <span>gates passed</span>
        <strong>{candidate.price}</strong>
        <span>per trial</span>
      </div>
      <div className={styles.gates}>
        {Object.entries(candidate.gate_results).map(([gate, ok]) => (
          <span className={ok ? styles.gatePass : styles.gateFail} key={gate}>
            {ok ? <Check size={12} /> : <CircleAlert size={12} />}
            {gate.replaceAll("_", " ").toLowerCase()}
          </span>
        ))}
      </div>
      <HashValue value={candidate.artifact_digest} />
    </article>
  );
}

function CompletedWorkspace({ proof }: { proof: ProofWorkspaceView }) {
  const digestIdentity =
    new Set([
      proof.activation.tested_adapter_digest,
      proof.activation.selected_adapter_digest,
      proof.authority.approved_adapter_digest,
      proof.activation.healthy_adapter_digest,
      proof.activation.active_adapter_digest,
    ]).size === 1;

  return (
    <div className={styles.workspaceGrid}>
      <main className={styles.mainColumn}>
        <section className={styles.heroCard} aria-labelledby="proof-summary">
          <div>
            <span className={styles.eyebrow}>Verified outcome · {proof.run_id}</span>
            <h2 id="proof-summary">DataHub changed the deployable winner.</h2>
            <p>{proof.summary}</p>
          </div>
          <div className={styles.sequence} aria-label="Causal winner sequence">
            {proof.context.causal_sequence.map((adapter, index) => (
              <span key={`${adapter}-${index}`}>
                <strong>{adapter.replace("adapter-", "").toUpperCase()}</strong>
                {index < proof.context.causal_sequence.length - 1 ? (
                  <ArrowRight size={17} aria-hidden="true" />
                ) : null}
              </span>
            ))}
          </div>
        </section>

        <section className={styles.section} aria-labelledby="context-heading">
          <div className={styles.sectionHead}>
            <div>
              <span className={styles.step}>01 · Context</span>
              <h2 id="context-heading">The governed fact that mattered</h2>
            </div>
            <State>Live from DataHub</State>
          </div>
          <div className={styles.factRow}>
            <Database size={22} aria-hidden="true" />
            <div>
              <strong>{proof.context.decisive_fact}</strong>
              <span>Observed state: {proof.context.decisive_fact_state.toLowerCase()}</span>
            </div>
          </div>
          <div className={styles.requirements}>
            {proof.context.requirements.map((requirement) => (
              <span key={requirement}>
                <Check size={12} />
                {requirement.replaceAll("_", " ").toLowerCase()}
              </span>
            ))}
          </div>
        </section>

        <section className={styles.section} aria-labelledby="run-heading">
          <div className={styles.sectionHead}>
            <div>
              <span className={styles.step}>02 · Proof run</span>
              <h2 id="run-heading">Same test. Two seller releases.</h2>
            </div>
            <State>Decision replayed</State>
          </div>
          <div className={styles.candidateGrid}>
            {proof.proof_run.candidates.map((candidate) => (
              <Candidate candidate={candidate} key={candidate.adapter_id} />
            ))}
          </div>
        </section>

        <section className={styles.splitGrid}>
          <article className={styles.section}>
            <div className={styles.sectionHead}>
              <div>
                <span className={styles.step}>03 · Authority</span>
                <h2>Exact owner approval</h2>
              </div>
              <ShieldCheck size={22} aria-hidden="true" />
            </div>
            <dl className={styles.details}>
              <div>
                <dt>Authority</dt>
                <dd>{proof.authority.actor_role.replace("_", " ")}</dd>
              </div>
              <div>
                <dt>Subject</dt>
                <dd>
                  <HashValue value={proof.authority.approval_subject_hash} />
                </dd>
              </div>
              <div>
                <dt>Fresh reread</dt>
                <dd>{proof.authority.pre_effect_reread_matched ? "Matched" : "Blocked"}</dd>
              </div>
            </dl>
          </article>
          <article className={styles.section}>
            <div className={styles.sectionHead}>
              <div>
                <span className={styles.step}>04 · Activation</span>
                <h2>Real routed behavior</h2>
              </div>
              <State>Verified</State>
            </div>
            <div className={styles.identityLine}>
              <Fingerprint size={20} aria-hidden="true" />
              <strong>{digestIdentity ? "5-way digest identity" : "Identity mismatch"}</strong>
            </div>
            <p className={styles.muted}>Tested = selected = approved = healthy = active</p>
            <HashValue value={proof.activation.active_adapter_digest} />
          </article>
        </section>

        <section className={styles.section} aria-labelledby="receipt-heading">
          <div className={styles.sectionHead}>
            <div>
              <span className={styles.step}>05 · Receipt</span>
              <h2 id="receipt-heading">Historical proof, reread from DataHub</h2>
            </div>
            <State>Immutable core</State>
          </div>
          <div className={styles.receiptBand}>
            <div>
              <span>Receipt core</span>
              <HashValue value={proof.receipt.core_hash} />
            </div>
            <ArrowRight size={18} aria-hidden="true" />
            <div>
              <span>DataHub projection</span>
              <HashValue value={proof.receipt.datahub_projection_hash} />
            </div>
            <ArrowRight size={18} aria-hidden="true" />
            <strong>Reread matched</strong>
          </div>
        </section>

        <section className={styles.recovery} aria-labelledby="recovery-heading">
          <RotateCcw size={21} aria-hidden="true" />
          <div>
            <h2 id="recovery-heading">Original state restored</h2>
            <p>PII tag present. Control tag absent. Route returned to the prior digest.</p>
            {proof.recovery.writeback_failure ? (
              <p className={styles.failureProof}>
                Induced writeback failure: no receipt issued; rollback verified.
              </p>
            ) : null}
          </div>
          <State>Safe</State>
        </section>
      </main>

      <aside className={styles.inspector} aria-label="Proof inspector">
        <div className={styles.inspectorHead}>
          <span className={styles.eyebrow}>Inspector</span>
          <h2>Fact → receipt</h2>
          <p>Every handoff is bound to the next by an exact hash.</p>
        </div>
        <ol className={styles.trace}>
          {proof.trace.map((item, index) => (
            <li key={item.label}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div>
                <strong>{item.label}</strong>
                <HashValue value={item.value} />
              </div>
            </li>
          ))}
        </ol>
        <a
          className={styles.datahubLink}
          href="http://localhost:9002"
          target="_blank"
          rel="noreferrer"
        >
          Open local DataHub <ExternalLink size={14} />
        </a>
      </aside>
    </div>
  );
}

export function ProofWorkspace() {
  const queryClient = useQueryClient();
  const runner = useQuery({
    queryKey: ["proof-runner"],
    queryFn: () =>
      getBrowserApiClient().request("get_proof_run", { headers: buyerDevelopmentHeaders }),
    refetchInterval: (query) => (query.state.data?.status === "RUNNING" ? 2000 : false),
  });
  const workspace = useQuery({
    queryKey: ["proof-workspace", runner.data?.run_id],
    queryFn: () =>
      getBrowserApiClient().request("get_proof_workspace", { headers: buyerDevelopmentHeaders }),
    retry: false,
    enabled: runner.data?.status !== "RUNNING",
  });
  const start = useMutation({
    mutationFn: () =>
      getBrowserApiClient().request("start_proof_run", { headers: buyerDevelopmentHeaders }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["proof-runner"] });
      await queryClient.invalidateQueries({ queryKey: ["proof-workspace"] });
    },
  });
  const running = runner.data?.status === "RUNNING" || start.isPending;
  const failed =
    !running && (runner.data?.status === "FAILED" || start.isError || workspace.isError);

  return (
    <div className={styles.shell}>
      <header className={styles.topbar}>
        <div className={styles.brand}>
          <span>SIRA</span>
          <strong>Proof of Fit</strong>
        </div>
        <div className={styles.topActions}>
          <span className={styles.live}>
            <i /> DataHub live
          </span>
          <button
            className={styles.runButton}
            disabled={running}
            onClick={() => start.mutate()}
            type="button"
          >
            <Play size={15} fill="currentColor" />
            {running ? "Running proof…" : "Run verified proof"}
          </button>
        </div>
      </header>

      <div className={styles.content}>
        <div className={styles.titleRow}>
          <div>
            <span className={styles.eyebrow}>Internal software decision · support automation</span>
            <h1>Can this seller release safely run on our stack?</h1>
          </div>
          <State>
            {failed ? "Blocked" : workspace.data ? "Complete" : running ? "In progress" : "Ready"}
          </State>
        </div>
        {running ? (
          <section className={styles.emptyState} aria-live="polite">
            <div className={styles.spinner} />
            <h2>Running the governed proof</h2>
            <p>
              Reading DataHub, testing both releases, checking authority, activating, verifying, and
              restoring.
            </p>
            <p>
              The page updates automatically. The full proof and recovery can take several minutes.
            </p>
          </section>
        ) : failed ? (
          <section className={styles.emptyState} aria-live="assertive">
            <CircleAlert size={28} aria-hidden="true" />
            <h2>Verified evidence unavailable</h2>
            <p>
              The latest proof did not complete or its artifact could not be verified. Previous
              success evidence is hidden until a new run passes every gate.
            </p>
            <p className={styles.error}>
              {runner.data?.safe_error_code ?? "PROOF_EVIDENCE_UNAVAILABLE"}. Run{" "}
              <code>scripts\proof.cmd demo -Assert</code>, then refresh.
            </p>
          </section>
        ) : workspace.data ? (
          <CompletedWorkspace proof={workspace.data} />
        ) : (
          <section className={styles.emptyState}>
            <Database size={28} aria-hidden="true" />
            <h2>No verified run yet</h2>
            <p>Start the proof to test two seller releases against live DataHub context.</p>
            <button className={styles.runButton} onClick={() => start.mutate()} type="button">
              <Play size={15} fill="currentColor" /> Run verified proof
            </button>
          </section>
        )}
      </div>
    </div>
  );
}
