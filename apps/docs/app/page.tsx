import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen w-full max-w-5xl flex-col justify-center px-6 py-20">
      <p className="text-sm font-medium text-fd-muted-foreground">
        VM on Golem
      </p>
      <h1 className="mt-3 max-w-3xl text-4xl font-semibold tracking-tight text-fd-foreground md:text-5xl">
        Documentation
      </h1>
      <p className="mt-5 max-w-2xl text-base leading-7 text-fd-muted-foreground">
        Role scoped guides for renting virtual machines, hosting provider
        capacity, and understanding the VM on Golem stack.
      </p>
      <div className="mt-8">
        <Link
          href="/docs"
          className="inline-flex h-10 items-center rounded-md bg-fd-primary px-4 text-sm font-medium text-fd-primary-foreground"
        >
          Open docs
        </Link>
      </div>
    </main>
  );
}
