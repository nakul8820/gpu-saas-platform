"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { authAPI, tokensAPI, jobsAPI } from "@/lib/api";
import Link from "next/link";

export default function Dashboard() {
    const router = useRouter();
    const [user, setUser] = useState<any>(null);
    const [balance, setBalance] = useState(0);
    const [jobs, setJobs] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const token = localStorage.getItem("access_token");
        if (!token) { router.push("/"); return; }
        loadData();
    }, []);

    const loadData = async () => {
        try {
            const [userRes, balRes, jobsRes] = await Promise.all([
                authAPI.me(),
                tokensAPI.getBalance(),
                jobsAPI.getAll(),
            ]);
            setUser(userRes.data);
            setBalance(balRes.data.balance);
            setJobs(jobsRes.data);
        } catch (e) {
            router.push("/");
        } finally {
            setLoading(false);
        }
    };

    const logout = () => {
        localStorage.removeItem("access_token");
        router.push("/");
    };

    const statusColor: any = {
        queued: "bg-yellow-900/40 text-yellow-400 border-yellow-700",
        dispatched: "bg-blue-900/40 text-blue-400 border-blue-700",
        running: "bg-green-900/40 text-green-400 border-green-700",
        completed: "bg-gray-800 text-gray-400 border-gray-700",
        failed: "bg-red-900/40 text-red-400 border-red-700",
    };

    if (loading) return (
        <div className="min-h-screen bg-gray-950 flex items-center justify-center">
            <p className="text-gray-400">Loading...</p>
        </div>
    );

    const running = jobs.filter(j => j.status === "running").length;
    const completed = jobs.filter(j => j.status === "completed").length;
    const failed = jobs.filter(j => j.status === "failed").length;

    return (
        <div className="min-h-screen bg-gray-950 text-white">

            {/* Navbar */}
            <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
                <div className="flex items-center gap-6">
                    <span className="text-lg font-bold text-indigo-400">GPU Platform</span>
                    <Link href="/dashboard" className="text-sm text-white">Dashboard</Link>
                    <Link href="/jobs" className="text-sm text-gray-400 hover:text-white">Jobs</Link>
                    <Link href="/billing" className="text-sm text-gray-400 hover:text-white">Billing</Link>
                </div>
                <div className="flex items-center gap-4">
                    <span className="text-sm text-gray-400">{user?.email}</span>
                    <button onClick={logout} className="text-sm text-gray-400 hover:text-white">Logout</button>
                </div>
            </nav>

            <div className="max-w-5xl mx-auto px-6 py-8">

                {/* Welcome */}
                <h1 className="text-2xl font-bold mb-6">
                    Welcome back, {typeof user?.full_name === 'string' && user.full_name !== 'string' ? user.full_name : user?.email} 👋
                </h1>

                {/* Stat cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    {[
                        { label: "Token balance", value: balance.toLocaleString(), color: "text-indigo-400" },
                        { label: "Running jobs", value: running, color: "text-green-400" },
                        { label: "Completed", value: completed, color: "text-gray-300" },
                        { label: "Failed", value: failed, color: "text-red-400" },
                    ].map((s) => (
                        <div key={s.label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                            <p className="text-xs text-gray-500 mb-1">{s.label}</p>
                            <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                        </div>
                    ))}
                </div>

                {/* Quick actions */}
                <div className="flex gap-3 mb-8">
                    <Link href="/jobs"
                        className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors">
                        Submit a job
                    </Link>
                    <Link href="/billing"
                        className="bg-gray-800 hover:bg-gray-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors">
                        Buy tokens
                    </Link>
                    <button onClick={loadData}
                        className="bg-gray-800 hover:bg-gray-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors">
                        Refresh
                    </button>
                </div>

                {/* Recent jobs */}
                <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                    <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
                        <h2 className="font-semibold">Recent jobs</h2>
                        <Link href="/jobs" className="text-sm text-indigo-400 hover:text-indigo-300">View all</Link>
                    </div>

                    {jobs.length === 0 ? (
                        <div className="px-6 py-12 text-center text-gray-500">
                            <p>No jobs yet.</p>
                            <Link href="/jobs" className="text-indigo-400 hover:text-indigo-300 text-sm mt-2 inline-block">
                                Submit your first job →
                            </Link>
                        </div>
                    ) : (
                        <div className="divide-y divide-gray-800">
                            {jobs.slice(0, 5).map((job) => (
                                <Link href={`/jobs/${job.id}`} key={job.id}
                                    className="flex items-center gap-4 px-6 py-4 hover:bg-gray-800/50 transition-colors">
                                    <span className={`text-xs px-2 py-1 rounded border ${statusColor[job.status] || "bg-gray-800 text-gray-400 border-gray-700"}`}>
                                        {job.status}
                                    </span>
                                    <span className="text-sm text-gray-300 font-mono flex-1 truncate">{job.docker_image}</span>
                                    <span className="text-xs text-gray-500">{job.tokens_locked} tokens locked</span>
                                    <span className="text-xs text-gray-600">
                                        {new Date(job.queued_at).toLocaleTimeString()}
                                    </span>
                                </Link>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}