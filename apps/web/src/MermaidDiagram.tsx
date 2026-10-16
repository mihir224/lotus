import { useEffect, useId, useState } from "react";

type Props = { title: string; source: string; theme: "dark" | "light" };

export function MermaidDiagram({ title, source, theme }: Props) {
  const reactId = useId().replace(/:/g, "");
  const [svg, setSvg] = useState("");
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError(false);
    void import("mermaid").then(({ default: mermaid }) => {
      mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: theme === "dark" ? "dark" : "neutral",
        flowchart: { htmlLabels: false }
      });
      return mermaid.render(`lotus-${reactId}`, source);
    })
      .then(({ svg: rendered }) => {
        if (!cancelled) setSvg(rendered);
      })
      .catch(() => {
        if (!cancelled) {
          setSvg("");
          setError(true);
        }
      });
    return () => { cancelled = true; };
  }, [reactId, source, theme]);

  return (
    <figure className="mermaid-artifact" aria-label={title}>
      <figcaption>{title}</figcaption>
      {error ? (
        <div className="mermaid-fallback">
          <p>The diagram could not be rendered.</p>
          <pre>{source}</pre>
        </div>
      ) : (
        <div className="mermaid-svg" dangerouslySetInnerHTML={{ __html: svg }} />
      )}
    </figure>
  );
}
