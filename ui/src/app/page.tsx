import Link from "next/link";

export default function Home() {
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">Trinetra</h1>
      <p className="text-gray-600">
        Insurance decisioning + monitoring dashboard.
      </p>
      <Link className="underline" href="/dashboard">
        Go to Dashboard →
      </Link>
    </div>
  );
}