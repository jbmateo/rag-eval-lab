import { getIndex } from "@/lib/data";

export default async function Home() {
  const index = await getIndex();
  return <main>{index.experiments.length} experiments</main>;
}
