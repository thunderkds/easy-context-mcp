import React from "react";

type Props = { label: string };

export const Badge = ({ label }: Props) => <span className="badge">{label}</span>;

export function BadgeList({ labels }: { labels: string[] }) {
  return <div>{labels.map((l) => <Badge label={l} />)}</div>;
}
