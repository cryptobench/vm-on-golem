import { DocsPage, DocsBody, DocsDescription, DocsTitle } from "fumadocs-ui/page";
import { notFound } from "next/navigation";
import { getMDXComponents } from "../../../components/mdx";
import { source } from "../../../lib/source";

export default async function Page(props: PageProps<"/docs/[[...slug]]">) {
  const params = await props.params;
  const page = source.getPage(params.slug);

  if (!page) {
    if (!params.slug || params.slug.length === 0) {
      return (
        <DocsPage toc={[]} full>
          <DocsTitle>Documentation</DocsTitle>
          <DocsDescription>
            No documentation pages have been added yet.
          </DocsDescription>
          <DocsBody>
            <p>
              Add MDX files under <code>content/docs</code> when the first docs
              are ready.
            </p>
          </DocsBody>
        </DocsPage>
      );
    }

    notFound();
  }

  const MDX = page.data.body;

  return (
    <DocsPage toc={page.data.toc} full={page.data.full}>
      <DocsTitle>{page.data.title}</DocsTitle>
      <DocsDescription>{page.data.description}</DocsDescription>
      <DocsBody>
        <MDX components={getMDXComponents()} />
      </DocsBody>
    </DocsPage>
  );
}

export function generateStaticParams() {
  return source.generateParams();
}

export async function generateMetadata(props: PageProps<"/docs/[[...slug]]">) {
  const params = await props.params;
  const page = source.getPage(params.slug);

  if (!page) {
    return {
      title: "Documentation",
      description: "VM on Golem documentation.",
    };
  }

  return {
    title: page.data.title,
    description: page.data.description,
  };
}
