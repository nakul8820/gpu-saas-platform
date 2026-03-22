"use client";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState, useEffect } from "react";

const stats = [
  { value: "10x", label: "Cheaper than AWS" },
  { value: "< 5s", label: "Job dispatch time" },
  { value: "20%", label: "Platform fee only" },
  { value: "100%", label: "Uptime SLA target" },
];

const userSteps = [
  { n: "01", title: "Create account", desc: "Sign up in 30 seconds. No credit card required to explore." },
  { n: "02", title: "Buy tokens", desc: "Purchase token packages starting at ₹199. Tokens never expire." },
  { n: "03", title: "Submit your job", desc: "Paste a Docker image, set runtime, click submit. Your job runs in seconds." },
];

const providerSteps = [
  { n: "01", title: "Register your GPU", desc: "Tell us your GPU model, VRAM, and location. Takes 2 minutes." },
  { n: "02", title: "Install the agent", desc: "One command on your Linux server. The agent handles everything automatically." },
  { n: "03", title: "Earn while you sleep", desc: "Jobs run on your GPU automatically. Withdraw earnings to your bank via UPI." },
];

const gpus = [
  { model: "NVIDIA T4", vram: "16 GB", tokens: 15, inr: "₹0.75", use: "Inference, light training" },
  { model: "NVIDIA RTX 3090", vram: "24 GB", tokens: 25, inr: "₹1.25", use: "Training, rendering" },
  { model: "NVIDIA RTX 4090", vram: "24 GB", tokens: 40, inr: "₹2.00", use: "Fast training, LLMs" },
  { model: "NVIDIA V100", vram: "32 GB", tokens: 60, inr: "₹3.00", use: "Large models, research" },
  { model: "NVIDIA A100", vram: "80 GB", tokens: 100, inr: "₹5.00", use: "Production AI, LLMs" },
  { model: "NVIDIA H100", vram: "80 GB", tokens: 180, inr: "₹9.00", use: "Frontier models" },
];

export default function Landing() {
  const router = useRouter();
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="min-h-screen bg-gray-950 text-white">

      {/* Navbar */}
      <nav className={`fixed top-0 left-0 right-0 z-50 transition-all duration-200 ${scrolled ? "bg-gray-950/95 border-b border-gray-800 backdrop-blur-sm" : ""}`}>
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center text-sm font-bold">G</div>
            <span className="font-bold text-white">GPU Platform</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            <a href="#how-it-works" className="text-sm text-gray-400 hover:text-white transition-colors">How it works</a>
            <a href="#pricing" className="text-sm text-gray-400 hover:text-white transition-colors">Pricing</a>
            <a href="#providers" className="text-sm text-gray-400 hover:text-white transition-colors">For providers</a>
          </div>
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-sm text-gray-400 hover:text-white transition-colors">
              Sign in
            </Link>
            <Link href="/login" className="text-sm bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg transition-colors font-medium">
              Get started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-indigo-950 border border-indigo-800 rounded-full px-4 py-1.5 text-xs text-indigo-300 mb-8">
            <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-pulse inline-block" />
            GPU compute marketplace — pay per second
          </div>
          <h1 className="text-5xl md:text-7xl font-bold leading-tight mb-6">
            Rent GPUs.<br />
            <span className="text-indigo-400">Pay per second.</span>
          </h1>
          <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            Access powerful GPUs from real providers — not hyperscalers.
            Run AI training, inference, and rendering jobs at a fraction of cloud prices.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/login"
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-8 py-4 rounded-xl text-lg transition-colors">
              Start computing →
            </Link>
            <a href="#providers"
              className="bg-gray-800 hover:bg-gray-700 text-white font-medium px-8 py-4 rounded-xl text-lg transition-colors">
              Earn with your GPU
            </a>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="py-12 px-6 border-y border-gray-800">
        <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-8">
          {stats.map((s) => (
            <div key={s.label} className="text-center">
              <p className="text-3xl font-bold text-indigo-400 mb-1">{s.value}</p>
              <p className="text-sm text-gray-500">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works — users */}
      <section id="how-it-works" className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-indigo-400 text-sm font-medium mb-2">FOR USERS</p>
            <h2 className="text-3xl md:text-4xl font-bold">Run your first job in minutes</h2>
          </div>
          <div className="grid md:grid-cols-3 gap-6">
            {userSteps.map((s) => (
              <div key={s.n} className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
                <p className="text-4xl font-bold text-gray-700 mb-4">{s.n}</p>
                <h3 className="text-lg font-semibold mb-2">{s.title}</h3>
                <p className="text-gray-400 text-sm leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
          <div className="text-center mt-10">
            <Link href="/login"
              className="inline-flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-6 py-3 rounded-xl transition-colors">
              Create free account →
            </Link>
          </div>
        </div>
      </section>

      {/* GPU Pricing */}
      <section id="pricing" className="py-20 px-6 bg-gray-900/50">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-indigo-400 text-sm font-medium mb-2">PRICING</p>
            <h2 className="text-3xl md:text-4xl font-bold">Pay only for what you use</h2>
            <p className="text-gray-400 mt-3">Billed per second. No minimums. No commitments.</p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
            <div className="grid grid-cols-4 px-6 py-3 border-b border-gray-800 text-xs text-gray-500 font-medium uppercase tracking-wide">
              <span>GPU</span>
              <span>VRAM</span>
              <span>Tokens / hr</span>
              <span>Best for</span>
            </div>
            {gpus.map((g, i) => (
              <div key={g.model} className={`grid grid-cols-4 px-6 py-4 items-center ${i !== gpus.length - 1 ? "border-b border-gray-800" : ""} ${g.model.includes("A100") ? "bg-indigo-950/30" : ""}`}>
                <div>
                  <p className="text-sm font-medium text-white">{g.model}</p>
                  {g.model.includes("A100") && <span className="text-xs bg-indigo-600 text-white px-2 py-0.5 rounded-full">Popular</span>}
                </div>
                <p className="text-sm text-gray-300">{g.vram}</p>
                <div>
                  <p className="text-sm font-medium text-indigo-400">{g.tokens} tokens</p>
                  <p className="text-xs text-gray-500">{g.inr}/hr</p>
                </div>
                <p className="text-xs text-gray-400">{g.use}</p>
              </div>
            ))}
          </div>
          <p className="text-center text-sm text-gray-500 mt-4">
            500 tokens = ₹199. 1 hour on A100 = 100 tokens = ₹5.
          </p>
        </div>
      </section>

      {/* For providers */}
      <section id="providers" className="py-20 px-6">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-14">
            <p className="text-green-400 text-sm font-medium mb-2">FOR GPU OWNERS</p>
            <h2 className="text-3xl md:text-4xl font-bold">Your GPU earns money while you sleep</h2>
            <p className="text-gray-400 mt-3 max-w-xl mx-auto">
              Got an NVIDIA GPU sitting idle? Connect it to our platform and earn passive income every time someone rents your compute.
            </p>
          </div>
          <div className="grid md:grid-cols-3 gap-6 mb-12">
            {providerSteps.map((s) => (
              <div key={s.n} className="bg-gray-900 border border-gray-800 rounded-2xl p-6">
                <p className="text-4xl font-bold text-gray-700 mb-4">{s.n}</p>
                <h3 className="text-lg font-semibold mb-2">{s.title}</h3>
                <p className="text-gray-400 text-sm leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>

          {/* Earnings calculator */}
          <div className="bg-gradient-to-br from-gray-900 to-gray-800 border border-gray-700 rounded-2xl p-8">
            <h3 className="text-xl font-bold mb-6 text-center">Estimate your earnings</h3>
            <div className="grid md:grid-cols-3 gap-6 text-center">
              {[
                { gpu: "RTX 4090", daily: "₹80–160", monthly: "₹2,400–4,800", hours: "8 hrs/day" },
                { gpu: "A100 80GB", daily: "₹200–400", monthly: "₹6,000–12,000", hours: "8 hrs/day" },
                { gpu: "H100", daily: "₹360–720", monthly: "₹10,800–21,600", hours: "8 hrs/day" },
              ].map((e) => (
                <div key={e.gpu} className="bg-gray-900 rounded-xl p-5 border border-gray-700">
                  <p className="text-sm font-medium text-gray-300 mb-1">{e.gpu}</p>
                  <p className="text-2xl font-bold text-green-400 mb-1">{e.monthly}</p>
                  <p className="text-xs text-gray-500">per month est. ({e.hours})</p>
                </div>
              ))}
            </div>
            <p className="text-center text-xs text-gray-600 mt-4">Estimates based on 50% utilization. Actual earnings vary.</p>
          </div>

          <div className="text-center mt-10">
            <Link href="/login"
              className="inline-flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white font-medium px-8 py-4 rounded-xl text-lg transition-colors">
              Start earning →
            </Link>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20 px-6 bg-indigo-950/40 border-y border-indigo-900/50">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">Ready to get started?</h2>
          <p className="text-gray-400 mb-8 text-lg">Join the GPU compute marketplace. No commitments, pay as you go.</p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/login"
              className="bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-8 py-4 rounded-xl text-lg transition-colors">
              Create free account
            </Link>
            <Link href="/login"
              className="bg-gray-800 hover:bg-gray-700 text-white font-medium px-8 py-4 rounded-xl text-lg transition-colors">
              Register your GPU
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 px-6 border-t border-gray-800">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-indigo-600 rounded flex items-center justify-center text-xs font-bold">G</div>
            <span className="text-sm font-medium">GPU Platform</span>
          </div>
          <p className="text-sm text-gray-600">GPU compute marketplace. Pay per second.</p>
          <div className="flex gap-6">
            <Link href="/login" className="text-sm text-gray-500 hover:text-white transition-colors">Sign in</Link>
            <Link href="/login" className="text-sm text-gray-500 hover:text-white transition-colors">Register</Link>
            <a href="#pricing" className="text-sm text-gray-500 hover:text-white transition-colors">Pricing</a>
          </div>
        </div>
      </footer>

    </div>
  );
}