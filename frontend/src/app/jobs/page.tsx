"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { jobsAPI, serversAPI } from "@/lib/api";
import Link from "next/link";

export default function Jobs() {
    const router = useRouter();
    const [jobs, setJobs] = useState<any[]>([]);
    const [servers, setServers] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    const [form, setForm] = useState({
        docker_image: "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
        max_runtime_minutes: 60,
        gpu_count: 1,
        required_vram_mb: 0,
        priority: 5,
    });

    useEffect(() => {
        const token = localStorage.getItem("access_token");
        if (!token) { router.push("/"); return; }
        loadData();
    }, []);

    const loadData = async () => {
        try {
            const [jobsRes, serversRes] = await Promise.all([
                jobsAPI.getAll(),
                serversAPI.getAvailable(),
            ]);
            setJobs(jobsRes.data);
            setServers(serversRes.data);
        } finally {
            setLoading(false);
        }
    };

    const submitJob = async () => {
        setSubmitting(true);
        setError("");
        setSuccess("");
        try {
            const res = await jobsAPI.submit(form);
            setSuccess(`Job submitted! ID: ${res.data.job_id} — ${res.data.tokens_locked} tokens locked`);
            loadData();
        } catch (e: any) {
            setError(e.response?.data?.detail || "Failed to submit job");
        } finally {
            setSubmitting(false);
        }
    };

    const statusColor: any = {
        queued: "text-yellow-400",
        dispatched: "text-blue-400",
        running: "text-green-400",
        completed: "text-gray-400",
        failed: "text-red-400",
    };

    if (loading) return (
        <div className="min-h-screen bg-gray-950 flex items-center justify-center">
            <p className="text-gray-400">Loading...</p>
        </div>
    );

    return (
        <div className="min-h-screen bg-gray-950 text-white">

            {/* Navbar */}
            <nav className="border-b border-gray-800 px-6 py-4 flex items-center gap-6">
                <span className="text-lg font-bold text-indigo-400">GPU Platform</span>
                <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white">Dashboard</Link>
                <Link href="/jobs" className="text-sm text-white">Jobs</Link>
                <Link href="/billing" className="text-sm text-gray-400 hover:text-white">Billing</Link>
            </nav>

            <div className="max-w-5xl mx-auto px-6 py-8 grid grid-cols-1 md:grid-cols-2 gap-8">

                {/* Submit form */}
                <div>
                    <h2 className="text-xl font-bold mb-4">Submit a job</h2>

                    {/* Available servers */}
                    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 mb-4">
                        <p className="text-xs text-gray-500 mb-2">Available GPU servers</p>
                        {servers.length === 0 ? (
                            <p className="text-sm text-red-400">No servers online right now</p>
                        ) : (
                            servers.map((s) => (
                                <div key={s.id} className="flex items-center justify-between">
                                    <span className="text-sm text-gray-300">{s.gpu_model}</span>
                                    <span className="text-xs text-indigo-400">{s.tokens_per_gpu_hour} tokens/hr</span>
                                </div>
                            ))
                        )}
                    </div>

                    <div className="space-y-4">
                        <div>
                            <label className="block text-xs text-gray-400 mb-1">Docker image</label>
                            <input
                                value={form.docker_image}
                                onChange={e => setForm({ ...form, docker_image: e.target.value })}
                                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500 font-mono"
                            />
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">Max runtime (mins)</label>
                                <input
                                    type="number"
                                    value={form.max_runtime_minutes}
                                    onChange={e => setForm({ ...form, max_runtime_minutes: Number(e.target.value) })}
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">GPU count</label>
                                <input
                                    type="number"
                                    value={form.gpu_count}
                                    onChange={e => setForm({ ...form, gpu_count: Number(e.target.value) })}
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">Min VRAM (MB)</label>
                                <input
                                    type="number"
                                    value={form.required_vram_mb}
                                    onChange={e => setForm({ ...form, required_vram_mb: Number(e.target.value) })}
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-gray-400 mb-1">Priority (1-10)</label>
                                <input
                                    type="number"
                                    value={form.priority}
                                    onChange={e => setForm({ ...form, priority: Number(e.target.value) })}
                                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-indigo-500"
                                />
                            </div>
                        </div>
                    </div>

                    {error && <div className="mt-4 p-3 bg-red-900/40 border border-red-700 rounded-lg text-red-400 text-sm">{error}</div>}
                    {success && <div className="mt-4 p-3 bg-green-900/40 border border-green-700 rounded-lg text-green-400 text-sm">{success}</div>}

                    <button
                        onClick={submitJob}
                        disabled={submitting || servers.length === 0}
                        className="w-full mt-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-medium py-3 rounded-lg transition-colors"
                    >
                        {submitting ? "Submitting..." : "Submit job"}
                    </button>
                </div>

                {/* Job list */}
                <div>
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-xl font-bold">Your jobs</h2>
                        <button onClick={loadData} className="text-sm text-gray-400 hover:text-white">Refresh</button>
                    </div>
                    <div className="space-y-2">
                        {jobs.length === 0 ? (
                            <p className="text-gray-500 text-sm">No jobs yet.</p>
                        ) : (
                            jobs.map((job) => (
                                <Link href={`/jobs/${job.id}`} key={job.id}
                                    className="block bg-gray-900 border border-gray-800 rounded-xl p-4 hover:border-gray-600 transition-colors">
                                    <div className="flex items-center justify-between mb-1">
                                        <span className={`text-xs font-medium ${statusColor[job.status]}`}>
                                            {job.status.toUpperCase()}
                                        </span>
                                        <span className="text-xs text-gray-500">
                                            {new Date(job.queued_at).toLocaleString()}
                                        </span>
                                    </div>
                                    <p className="text-sm font-mono text-gray-300 truncate">{job.docker_image}</p>
                                    <div className="flex gap-4 mt-2">
                                        <span className="text-xs text-gray-500">Locked: {job.tokens_locked}</span>
                                        {job.tokens_billed && <span className="text-xs text-gray-500">Billed: {job.tokens_billed}</span>}
                                        {job.gpu_seconds_used && <span className="text-xs text-gray-500">{job.gpu_seconds_used}s GPU</span>}
                                    </div>
                                </Link>
                            ))
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}