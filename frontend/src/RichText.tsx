import { Fragment } from "react";

function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => (
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={`${part}-${index}`}>{part.slice(2, -2)}</strong>
      : <Fragment key={`${part}-${index}`}>{part}</Fragment>
  ));
}

export default function RichText({ children }: { children: string }) {
  const lines = children.split("\n");
  return lines.map((line, index) => (
    <Fragment key={`${line}-${index}`}>
      {inline(line)}
      {index < lines.length - 1 && <br />}
    </Fragment>
  ));
}
