export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl items-center px-6 py-16">
      <section className="w-full rounded-3xl border border-[var(--border)] bg-[var(--surface)] p-10 shadow-sm sm:p-14">
        <p className="mb-5 text-sm font-semibold tracking-[0.18em] text-[var(--accent)] uppercase">
          SIRA + SEIL
        </p>
        <h1 className="max-w-3xl text-4xl leading-tight font-semibold tracking-tight sm:text-6xl">
          Company-aware decisions, exact authority, verified outcomes.
        </h1>
        <p className="mt-6 max-w-2xl text-lg leading-8 text-[var(--muted)]">
          The web workspace is ready for the separate UI implementation. Shared screens consume the
          frozen OpenAPI client and deterministic demo fixtures.
        </p>
      </section>
    </main>
  );
}
