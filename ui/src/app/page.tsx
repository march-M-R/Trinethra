"use client";

import Link from "next/link";
import { useState } from "react";
import { BrandMark } from "@/components/Brand";
import { Icon } from "@/components/Workspace";

const capabilities = [
  { number: "01", icon: "file", title: "An informed beginning.", text: "Capture the claim essentials and bring policyholder context into one considered assessment.", detail: "CLAIM ASSESSMENT" },
  { number: "02", icon: "shield", title: "A signal worth understanding.", text: "See the model risk score, the decision threshold, and the reasoning recorded with every outcome.", detail: "RISK & CONTEXT" },
  { number: "03", icon: "search", title: "Human judgment, in focus.", text: "Bring flagged cases to a dedicated review queue, with the claim details close at hand.", detail: "REVIEW & OVERSIGHT" },
];

export default function Home() {
  const [paused, setPaused] = useState(false);
  return <div className="opening-page" data-motion={paused ? "paused" : "playing"}>
    <a className="skip-link" href="#opening-content">Skip to content</a>
    <header className="opening-nav"><Link href="/" className="opening-brand" aria-label="Trinetra home"><BrandMark/><span>TRINETRA<small>CLAIMS INTELLIGENCE</small></span></Link><nav aria-label="Main navigation"><a className="opening-nav-link" href="#approach">The approach</a><Link className="opening-workspace-link" href="/dashboard">Open workspace <Icon name="arrow" size={16}/></Link></nav></header>
    <main id="opening-content">
      <section className="opening-hero" aria-labelledby="opening-title">
        <div className="opening-copy"><div className="opening-eyebrow entrance">PERSPECTIVE. PRECISION. ASSURANCE.</div><h1 id="opening-title" className="entrance entrance-two">The third eye<br/>of <em>claim automation.</em></h1><p className="opening-description entrance entrance-three">See beyond the claim. Bring risk, context, and human judgment together for a clearer path forward.</p><div className="opening-actions entrance entrance-four"><Link href="/dashboard" className="opening-primary">Enter the workspace <Icon name="arrow" size={18}/></Link><a href="#approach" className="opening-secondary">Explore the approach <span aria-hidden="true">↗</span></a></div><div className="opening-caption entrance entrance-four"><span/>Built for clarity. Designed for considered decisions.</div></div>
        <div className="opening-art entrance entrance-three"><div className="orbital-scene" aria-hidden="true"><div className="orbit orbit-outer"/><div className="orbit orbit-middle"/><div className="orbit orbit-inner"/><div className="orbit-axis axis-one"/><div className="orbit-axis axis-two"/><span className="orbit-point point-one"/><span className="orbit-point point-two"/><span className="orbit-point point-three"/><div className="emblem-halo"/><BrandMark className="opening-emblem"/><span className="art-coordinate coordinate-top">01 / PERSPECTIVE</span><span className="art-coordinate coordinate-bottom">TRINETRA · THE THIRD EYE</span></div><button type="button" className="motion-control" aria-pressed={paused} onClick={() => setPaused(value => !value)}><span aria-hidden="true">{paused ? "▷" : "Ⅱ"}</span>{paused ? "Resume animation" : "Pause animation"}</button></div>
      </section>
      <div className="opening-principles"><span>ONE CONNECTED WORKSPACE</span><div><span>Claim assessment</span><i/><span>Risk intelligence</span><i/><span>Human review</span></div><a href="#approach" aria-label="Discover our approach">↓</a></div>
      <section className="opening-approach" id="approach" aria-labelledby="approach-title"><div className="approach-heading"><div><span className="opening-section-label">THE APPROACH</span><h2 id="approach-title">A clearer picture.<br/><em>A more considered decision.</em></h2></div><p>From the first detail to the final record, Trinetra brings structure to the moments that matter.</p></div><div className="capability-grid">{capabilities.map(item => <article className="capability" key={item.number}><div className="capability-top"><span>{item.number}</span><Icon name={item.icon} size={22}/></div><div className="capability-label">{item.detail}</div><h3>{item.title}</h3><p>{item.text}</p></article>)}</div></section>
      <section className="opening-close"><div><span className="opening-section-label">YOUR NEXT PERSPECTIVE</span><h2>Begin with a clearer view.</h2></div><Link href="/new-claim" className="opening-primary">Evaluate a claim <Icon name="arrow" size={18}/></Link></section>
    </main>
    <footer className="opening-footer"><span>TRINETRA <span className="footer-divider">/</span> The third eye of claim automation</span><p>A prototype for decision support. Risk scores do not confirm fraud.</p><Link href="/dashboard">Workspace <Icon name="arrow" size={14}/></Link></footer>
  </div>;
}
