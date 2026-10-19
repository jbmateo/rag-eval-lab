import { notFound } from "next/navigation";
import { ExperimentView } from "@/components/ExperimentView";
import { getExperiment, getIndex } from "@/lib/data";

export const dynamicParams = false;

export async function generateStaticParams() {
  const index = await getIndex();
  return index.experiments.length ? index.experiments.map((e) => ({ name: e.slug })) : [{ name: "none" }];
}

export default async function ExperimentPage({ params }: { params: Promise<{ name: string }> }) {
  const exp = await getExperiment((await params).name);
  if (!exp) notFound();
  return <ExperimentView exp={exp} />;
}
