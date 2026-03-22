"use client";
import { useEffect, useState, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { jobsAPI } from "@/lib/api";
import Link from "next/link";

export default function JobDetail() {
    const router = useRouter();
    const params = useParams();
    const jobId = params.id as string;

    const [job, setJob] = useState<any>(null);
    const [logs, setLogs] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [autoRefresh, setAutoRefresh] = useState(true);
    const logsEndRef = useRef<HTMLDivElement>(null);
    const intervalRef = useRef<any>(null);

    useEffect(() => {
        const token = localStorage.getItem("access_token");
        if (!token) { router.push("/"); return; }
        loadData();
    }, [jobId]);

    // Auto-scroll to bottom when new logs arrive
    useEffect(() => {
        if (autoRefresh) {
            logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
        }
    }, [logs]);

    // Auto-refresh every 3s while job is running
    useEffect(() => {
        if (autoRefresh) {
            intervalRef.current = setInterval(() => {
                loadData();
            }, 3000);
        }
        return () => clearInterval(intervalRef.current);
    }, [autoRefresh]);

    // Stop auto-refresh when job is done
    useEffect(() => {
        if (job && ["completed", "failed", "cancelled"].includes(job.status)) {
            setAutoRefresh(false);
        }
    }, [job?.status]);

    const loadData = async () => {
        try {
            const [jobRes, logsRes] = await Promise.all([
                jobsAPI.getById(jobId),
                jobsAPI.getLogs(jobId),
            ]);
            setJob(jobRes.data);
            setLogs(logsRes.data.logs);
        } catch (e) {
            router.push("/jobs");
        } finally {
            setLoading(false);
        }
    };

    const statusColor: any = {
        queued: { bg: "bg-yellow-900/30", text: "text-yellow-400", border: "border-yellow-700" },
        dispatched: { bg: "bg-blue-900/30", text: "text-blue-400", border: "border-blue-700" },
        running: { bg: "bg-green-900/30", text: "text-green-400", border: "border-green-700" },
        completed: { bg: "bg-gray-800", text: "text-gray-300", border: "border-gray-600" },
        failed: { bg: "bg-red-900/30", text: "text-red-400", border: "border-red-700" },
    };

    const sc = statusColor[job?.status] || statusColor.queued;

    if (loading) return (
        <div className="min-h-screen bg-gray-950 flex items-center justify-center">
            <p className="text-gray-400">Loading job...</p>
        </div>
    );

    const isActive = ["queued", "dispatched", "running"].includes(job?.status);

    return (
        <div className="min-h-screen bg-gray-950 text-white">

            {/* Navbar */}
            <nav className="border-b border-gray-800 px-6 py-4 flex items-center gap-6">
                <span className="text-lg font-bold text-indigo-400">GPU Platform</span>
                <Link href="/dashboard" className="text-sm text-gray-400 hover:text-white">Dashboard</Link>
                <Link href="/jobs" className="text-sm text-gray-400 hover:text-white">Jobs</Link>
                <Link href="/billing" className="text-sm text-gray-400 hover:text-white">Billing</Link>
            </nav>

            <div className="max-w-5xl mx-auto px-6 py-8">

                {/* Back */}
                <Link href="/jobs" className="text-sm text-gray-400 hover:text-white mb-6 inline-flex items-center gap-1">
                    ← Back to jobs
                </Link>

                {/* Job header */}
                <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 mb-6 mt-4">
                    <div className="flex items-start justify-between mb-4">
                        <div>
                            <span className={`inline-block text-xs px-3 py-1 rounded-full border ${sc.bg} ${sc.text} ${sc.border} mb-3`}>
                                {job?.status?.toUpperCase()}
                                {isActive && <span className="ml-2 inline-block w-1.5 h-1.5 bg-current rounded-full animate-pulse" />}
                            </span>
                            <p className="font-mono text-gray-200 text-sm">{job?.docker_image}</p>
                            <p className="text-xs text-gray-500 mt-1">Job ID: {jobId}</p>
                        </div>
                        <div className="text-right">
                            <button
                                onClick={() => setAutoRefresh(!autoRefresh)}
                                className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${autoRefresh
                                        ? "border-green-700 text-green-400 bg-green-900/20"
                                        : "border-gray-700 text-gray-400 bg-gray-800"
                                    }`}
                            >
                                {autoRefresh ? "● Auto-refresh on" : "○ Auto-refresh off"}
                            </button>
                        </div>
                    </div>

                    {/* Stats grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {[
                            { label: "Tokens locked", value: job?.tokens_locked ?? "—" },
                            { label: "Tokens billed", value: job?.tokens_billed ?? "pending" },
                            { label: "GPU seconds", value: job?.gpu_seconds_used ? `${job.gpu_seconds_used}s` : "—" },
                            { label: "Exit code", value: job?.exit_code ?? "—" },
                        ].map((s) => (
                            <div key={s.label} className="bg-gray-800 rounded-xl p-3">
                                <p className="text-xs text-gray-500 mb-1">{s.label}</p>
                                <p className="text-lg font-semibold text-white">{s.value}</p>
                            </div>
                        ))}
                    </div>

                    {/* Timing */}
                    <div className="flex gap-6 mt-4 text-xs text-gray-500">
                        {job?.queued_at && <span>Queued: {new Date(job.queued_at).toLocaleString()}</span>}
                        {job?.started_at && <span>Started: {new Date(job.started_at).toLocaleString()}</span>}
                        {job?.completed_at && <span>Completed: {new Date(job.completed_at).toLocaleString()}</span>}
                    </div>

                    {/* Error message */}
                    {job?.error_message && (
                        <div className="mt-4 p-3 bg-red-900/30 border border-red-700 rounded-lg text-red-400 text-sm">
                            {job.error_message}
                        </div>
                    )}
                </div>

                {/* Log viewer */}
                <div className="bg-gray-950 border border-gray-800 rounded-2xl overflow-hidden">

                    {/* Terminal header */}
                    <div className="flex items-center justify-between px-4 py-3 bg-gray-900 border-b border-gray-800">
                        <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full bg-red-500" />
                            <div className="w-3 h-3 rounded-full bg-yellow-500" />
                            <div className="w-3 h-3 rounded-full bg-green-500" />
                            <span className="ml-2 text-xs text-gray-500 font-mono">stdout</span>
                        </div>
                        <div className="flex items-center gap-3">
                            {isActive && (
                                <span className="text-xs text-green-400 flex items-center gap-1">
                                    <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse inline-block" />
                                    Live
                                </span>
                            )}
                            <span className="text-xs text-gray-600">{logs.length} lines</span>
                            <button
                                onClick={loadData}
                                className="text-xs text-gray-500 hover:text-white transition-colors"
                            >
                                Refresh
                            </button>
                        </div>
                    </div>

                    {/* Log content */}
                    <div className="h-96 overflow-y-auto p-4 font-mono text-sm">
                        {logs.length === 0 ? (
                            <div className="flex items-center justify-center h-full">
                                <div className="text-center">
                                    {isActive ? (
                                        <>
                                            <div className="flex gap-1 justify-center mb-3">
                                                <div className="w-2 h-2 bg-green-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                                                <div className="w-2 h-2 bg-green-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                                                <div className="w-2 h-2 bg-green-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                                            </div>
                                            <p className="text-gray-500 text-xs">Waiting for logs...</p>
                                        </>
                                    ) : (
                                        <p className="text-gray-600 text-xs">No logs recorded for this job.</p>
                                    )}
                                </div>
                            </div>
                        ) : (
                            <>
                                {logs.map((log, i) => (
                                    <div key={i} className="flex gap-3 mb-1 hover:bg-gray-900/50 px-1 rounded">
                                        <span className="text-gray-700 select-none w-6 text-right flex-shrink-0">
                                            {log.seq + 1}
                                        </span>
                                        <span className={
                                            log.stream === "stderr" ? "text-red-400" :
                                                log.chunk.includes("loss:") ? "text-green-400" :
                                                    log.chunk.includes("Error") ? "text-red-400" :
                                                        log.chunk.includes("Done") || log.chunk.includes("complete") ? "text-indigo-400" :
                                                            "text-gray-300"
                                        }>
                                            {log.chunk}
                                        </span>
                                    </div>
                                ))}
                                <div ref={logsEndRef} />
                            </>
                        )}
                    </div>

                    {/* Terminal footer */}
                    <div className="px-4 py-2 bg-gray-900 border-t border-gray-800 flex items-center justify-between">
                        <span className="text-xs text-gray-600 font-mono">
                            {job?.gpu_model && `GPU: ${job.gpu_model}`}
                        </span>
                        <span className="text-xs text-gray-600 font-mono">
                            {isActive ? "running..." : `exit ${job?.exit_code ?? "—"}`}
                        </span>
                    </div>
                </div>

                {/* Billing summary — shown after completion */}
                {job?.status === "completed" && (
                    <div className="mt-6 bg-gray-900 border border-gray-800 rounded-2xl p-6">
                        <h3 className="font-semibold mb-4 text-green-400">Job completed successfully</h3>
                        <div className="grid grid-cols-3 gap-4 text-center">
                            <div>
                                <p className="text-2xl font-bold text-white">{job.tokens_locked}</p>
                                <p className="text-xs text-gray-500 mt-1">Tokens locked</p>
                            </div>
                            <div>
                                <p className="text-2xl font-bold text-red-400">{job.tokens_billed}</p>
                                <p className="text-xs text-gray-500 mt-1">Tokens billed</p>
                            </div>
                            <div>
                                <p className="text-2xl font-bold text-blue-400">{job.tokens_locked - (job.tokens_billed || 0)}</p>
                                <p className="text-xs text-gray-500 mt-1">Tokens refunded</p>
                            </div>
                        </div>
                    </div>
                )}

                {job?.status === "failed" && (
                    <div className="mt-6 bg-red-900/20 border border-red-800 rounded-2xl p-6">
                        <h3 className="font-semibold mb-2 text-red-400">Job failed</h3>
                        <p className="text-sm text-gray-400">All locked tokens have been refunded to your balance.</p>
                    </div>
                )}

            </div>
        </div>
    );
}