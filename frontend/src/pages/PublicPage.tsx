import { useEffect } from "react"

type PublicPageProps = { path: string }

type Article = {
  title: string
  description: string
  sections: { heading: string; body: string }[]
}

const ARTICLES: Record<string, Article> = {
  "/learn/what-is-requirement-ambiguity": {
    title: "What is requirement ambiguity?",
    description: "Learn how unclear software requirements create different interpretations and avoidable rework.",
    sections: [
      { heading: "A requirement has more than one reading", body: "A requirement is ambiguous when reasonable readers can interpret its words, structure, meaning, or intended context differently. The risk is practical: engineers, testers, and stakeholders may implement or approve different behaviors." },
      { heading: "The four useful categories", body: "Lexical ambiguity comes from overloaded words. Syntactic ambiguity comes from sentence structure. Semantic ambiguity comes from unclear meaning or references. Pragmatic ambiguity comes from missing context, measures, assumptions, or acceptance criteria." },
      { heading: "How to reduce the risk", body: "Name the actor, action, object, conditions, limits, and measurable outcome. Then ask whether two people could test the requirement and reach different conclusions." },
    ],
  },
  "/learn/lexical-ambiguity": {
    title: "Lexical ambiguity in software requirements",
    description: "Understand overloaded words and replace them with precise, testable language.",
    sections: [
      { heading: "What it looks like", body: "Words such as process, manage, current, appropriate, and details can hide multiple possible operations or meanings. The issue is the word choice itself, not necessarily the whole sentence." },
      { heading: "Example", body: "‘The system shall process the request’ does not say whether processing means validating, approving, routing, or completing it. Name the exact operation and outcome." },
      { heading: "A practical test", body: "Circle the verbs and nouns that could reasonably be replaced by two different words. Define the domain term or split the requirement into explicit actions." },
    ],
  },
  "/learn/syntactic-ambiguity": {
    title: "Syntactic ambiguity in software requirements",
    description: "See how sentence structure and attachment create competing readings.",
    sections: [
      { heading: "Structure changes meaning", body: "A phrase such as ‘display reports for managers’ can describe the audience, the report owner, or the purpose. Coordination and misplaced modifiers often create this kind of ambiguity." },
      { heading: "Make relationships explicit", body: "Use short sentences, name the actor, and place conditions next to the action they govern. Avoid long chains of and, or, and only when the relationship matters." },
      { heading: "Test the rewrite", body: "Ask a reviewer to paraphrase the requirement without seeing your intended design. If the paraphrase changes the subject or condition, clarify the structure." },
    ],
  },
  "/learn/semantic-ambiguity": {
    title: "Semantic ambiguity in software requirements",
    description: "Clarify references, scope, and domain meaning before implementation begins.",
    sections: [
      { heading: "Meaning depends on missing definitions", body: "Semantic ambiguity occurs when a phrase can refer to different entities, states, relationships, or scopes. ‘Delete duplicate entries’ needs a definition of duplicate." },
      { heading: "Resolve references", body: "Replace pronouns such as it, they, and this with the specific entity. Define which fields, roles, records, and states are included." },
      { heading: "Connect to acceptance tests", body: "A good semantic clarification gives a tester a finite set of facts to verify, rather than asking them to infer the intended domain rule." },
    ],
  },
  "/learn/pragmatic-ambiguity": {
    title: "Pragmatic ambiguity in software requirements",
    description: "Learn why missing context, measures, and acceptance criteria make requirements difficult to test.",
    sections: [
      { heading: "The requirement depends on assumptions", body: "Pragmatic ambiguity appears when the words may be understandable but the requirement omits context that different stakeholders will supply differently." },
      { heading: "Common signals", body: "Quickly, soon, easy, reliable, many, as needed, and appropriate can be valid in conversation but are risky in a specification when no threshold or condition follows." },
      { heading: "Make it measurable", body: "Replace ‘respond quickly’ with a response-time limit, workload, and operating condition. A measurable criterion lets teams implement, test, and negotiate the same expectation." },
    ],
  },
  "/learn/how-to-write-clear-software-requirements": {
    title: "How to write clear software requirements",
    description: "A practical checklist for writing requirements that teams can build and test consistently.",
    sections: [
      { heading: "Use a complete statement", body: "Name the system or actor, the required action, the object, and the trigger or condition. Prefer one observable behavior per sentence." },
      { heading: "Define measurable boundaries", body: "Specify quantities, time limits, quality thresholds, roles, error behavior, and relevant edge cases. Avoid relying on adjectives that different readers will grade differently." },
      { heading: "Review for interpretation", body: "Have someone outside the drafting conversation explain what the requirement means and how they would test it. Revise anything they must guess." },
    ],
  },
  "/learn/ambiguous-requirement-examples": {
    title: "Ambiguous requirement examples",
    description: "Study common ambiguity patterns and see how precise rewrites improve testability.",
    sections: [
      { heading: "Unmeasured performance", body: "Ambiguous: ‘The system shall respond quickly.’ Clearer: ‘The system shall return a response within 2 seconds for requests up to 500 KB under normal operating conditions.’" },
      { heading: "Undefined scope", body: "Ambiguous: ‘The system shall show relevant information.’ Clearer: ‘The system shall show account ID, status, owner, and last-updated date to account managers.’" },
      { heading: "Unclear actor", body: "Ambiguous: ‘Reports shall be reviewed.’ Clearer: ‘The compliance manager shall approve each monthly report before publication.’" },
    ],
  },
}

const pageMeta: Record<string, { title: string; description: string }> = {
  "/about": { title: "About Requirement Ambiguity AI", description: "Requirement Ambiguity AI, created by Alishba Nazem, helps teams write clearer software requirements." },
  "/privacy": { title: "Privacy | Requirement Ambiguity AI", description: "How Requirement Ambiguity AI handles requirement text, uploads, analytics, and future advertising." },
  "/terms": { title: "Terms | Requirement Ambiguity AI", description: "Terms for using Requirement Ambiguity AI as a requirement analysis tool." },
  ...Object.fromEntries(Object.entries(ARTICLES).map(([path, article]) => [path, { title: article.title, description: article.description }])),
}

function AnalyzeLink() {
  return <a className="font-semibold text-primary hover:underline" href="/analyze">Analyze your requirement with Requirement Ambiguity AI</a>
}

export function PublicPage({ path }: PublicPageProps) {
  const article = ARTICLES[path]
  const meta = pageMeta[path] ?? { title: "Requirement Ambiguity AI", description: "Analyze software requirements for ambiguity and improve them with clear, testable suggestions." }

  useEffect(() => {
    document.title = meta.title
    const description = document.querySelector('meta[name="description"]')
    description?.setAttribute("content", meta.description)
    const canonical = document.querySelector('link[rel="canonical"]')
    const siteUrl = (import.meta.env.VITE_SITE_URL || window.location.origin).replace(/\/$/, "")
    canonical?.setAttribute("href", `${siteUrl}${path}`)
  }, [meta.description, meta.title, path])

  return (
    <div className="mx-auto max-w-[820px] px-5 py-12 sm:py-16">
      <p className="text-[12px] font-semibold uppercase tracking-[0.14em] text-primary">Requirement Ambiguity AI</p>
      {article ? <ArticlePage article={article} /> : <StaticPage path={path} />}
    </div>
  )
}

function ArticlePage({ article }: { article: Article }) {
  return (
    <article>
      <h1 className="mt-3 max-w-[720px] text-4xl font-semibold leading-tight text-ink sm:text-5xl">{article.title}</h1>
      <p className="mt-5 max-w-[680px] text-lg leading-8 text-muted">{article.description}</p>
      <div className="mt-10 space-y-9">
        {article.sections.map((section) => (
          <section key={section.heading}>
            <h2 className="text-2xl font-semibold">{section.heading}</h2>
            <p className="mt-2 max-w-[700px] text-[16px] leading-8 text-muted">{section.body}</p>
          </section>
        ))}
      </div>
      <p className="mt-12 border-t border-line pt-6"><AnalyzeLink /></p>
    </article>
  )
}

function StaticPage({ path }: { path: string }) {
  if (path === "/about") return <article><h1 className="mt-3 text-4xl font-semibold">Requirement Ambiguity AI</h1><p className="mt-5 text-lg leading-8 text-muted">Created by Alishba Nazem, Requirement Ambiguity AI is a focused tool for identifying unclear software requirements and turning them into more testable statements.</p><p className="mt-8"><AnalyzeLink /></p></article>
  if (path === "/privacy") return <article><h1 className="mt-3 text-4xl font-semibold">Privacy</h1><p className="mt-5 text-[16px] leading-8 text-muted">Requirement text is sent to the configured analysis service when you submit it. Uploaded documents are parsed in the application flow. This repository does not provide a user account or persistent history database; deployment operators must document their own provider logs, retention, analytics, and storage settings. No analytics provider is enabled by default. Future advertising or premium features will require updated disclosure.</p><p className="mt-8"><AnalyzeLink /></p></article>
  if (path === "/terms") return <article><h1 className="mt-3 text-4xl font-semibold">Terms</h1><p className="mt-5 text-[16px] leading-8 text-muted">Use Requirement Ambiguity AI as an assistance tool, not as a substitute for domain review, security review, legal advice, or formal requirements approval. You are responsible for the text you submit and for validating suggested rewrites before using them. Service availability and third-party provider behavior depend on the deployment configuration.</p><p className="mt-8"><AnalyzeLink /></p></article>
  return <article><h1 className="mt-3 text-4xl font-semibold">Requirement Ambiguity AI</h1><p className="mt-5 text-lg leading-8 text-muted">Identify unclear wording, understand why it matters, and improve a requirement.</p><p className="mt-8"><AnalyzeLink /></p></article>
}
