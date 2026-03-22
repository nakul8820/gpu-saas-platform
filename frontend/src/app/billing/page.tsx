"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { tokensAPI } from "@/lib/api";
import Link from "next/link";

export default function Billing() {
    const router = useRouter();
    const [packages, setPackages] = useState<any[]>([]);
    const [history, setHistory] = useState<any[]>([]);
    const [balance, setBalance] = useState(0);
    const [loading, setLoading] = useState(true);
    const [buying, setBuying] = useState<string | null>(null);
    const [message, setMessage] = useState("");

    useEffect(() => {
        const token = localStorage.getItem("access_token");
        if (!token) { router.push("/"); return; }
        loadData();
    }, []);

    const loadData = async () => {
        try {
            const [pkgRes, balRes, histRes] = await Promise.all([
                tokensAPI.getPackages(),
                tokensAPI.getBalance(),
                tokensAPI.getHistory(),
            ]);
            setPackages(pkgRes.data);
            setBalance(balRes.data.balance);
            setHistory(histRes.data.entries);
        } finally {
            setLoading(false);
        }
    };

    const buyPackage = async (pkg: any) => {
        setBuying(pkg.id);
        setMessage("");
        try {
            await tokensAPI.purchase(pkg.id);
            setMessage(`✓ Added ${pkg.total_tokens} tokens to your account!`);
            loadData();
        } catch (e: any) {
            setMessage(e.response?.data?.detail || "Purchase failed");
        } finally {
            setBuying(null);
        }
    };

    const entryColor: any = {
        purchase: "text-green-400",
        job_lock: "text-yellow-400",
        job_debit: "text-red-400",
        job_lock_release: "text-blue-400",
        job_refund: "text-blue-400",
        admin_credit: "text-green-400",
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
                <Link href="/jobs" className="text-sm text-gray-400 hover:text-white">Jobs</Link>
                <Link href="/billing" className="text-sm text-white">Billing</Link>
            </nav>

            <div className="max-w-5xl mx-auto px-6 py-8">

                {/* Balance */}
                <div className="bg-indigo-900/30 border border-indigo-700 rounded-2xl p-6 mb-8">
                    <p className="text-sm text-indigo-300 mb-1">Current token balance</p>
                    <p className="text-5xl font-bold text-white">{balance.toLocaleString()}</p>
                    <p className="text-sm text-indigo-400 mt-1">tokens</p>
                </div>

                {message && (
                    <div className={`mb-6 p-4 rounded-lg border text-sm ${message.startsWith("✓")
                        ? "bg-green-900/40 border-green-700 text-green-400"
                        : "bg-red-900/40 border-red-700 text-red-400"
                        }`}>
                        {message}
                    </div>
                )}

                {/* Packages */}
                <h2 className="text-xl font-bold mb-4">Buy tokens</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
                    {packages.map((pkg) => (
                        <div key={pkg.id}
                            className="bg-gray-900 border border-gray-800 hover:border-indigo-600 rounded-xl p-5 transition-colors">
                            <p className="text-sm font-medium text-gray-300 mb-3">{pkg.name}</p>
                            <p className="text-3xl font-bold text-white mb-1">
                                {pkg.total_tokens.toLocaleString()}
                            </p>
                            <p className="text-xs text-gray-500 mb-4">tokens</p>
                            <p className="text-lg font-semibold text-indigo-400 mb-4">
                                ₹{pkg.price_inr}
                            </p>
                            <button
                                onClick={() => buyPackage(pkg)}
                                disabled={buying === pkg.id}
                                className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white text-sm font-medium py-2 rounded-lg transition-colors"
                            >
                                {buying === pkg.id ? "..." : "Buy"}
                            </button>
                        </div>
                    ))}
                </div>

                {/* Transaction history */}
                <h2 className="text-xl font-bold mb-4">Transaction history</h2>
                <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                    {history.length === 0 ? (
                        <p className="p-6 text-gray-500 text-sm">No transactions yet.</p>
                    ) : (
                        <div className="divide-y divide-gray-800">
                            {history.map((entry) => (
                                <div key={entry.id} className="flex items-center px-6 py-4 gap-4">
                                    <span className={`text-lg font-bold w-20 ${entry.amount > 0 ? "text-green-400" : "text-red-400"
                                        }`}>
                                        {entry.amount > 0 ? "+" : ""}{entry.amount}
                                    </span>
                                    <div className="flex-1">
                                        <p className={`text-xs font-medium ${entryColor[entry.entry_type] || "text-gray-400"}`}>
                                            {entry.entry_type.replace(/_/g, " ").toUpperCase()}
                                        </p>
                                        <p className="text-sm text-gray-400 truncate">{entry.description}</p>
                                    </div>
                                    <div className="text-right">
                                        <p className="text-sm text-gray-300">Balance: {entry.balance_after}</p>
                                        <p className="text-xs text-gray-600">
                                            {new Date(entry.created_at).toLocaleString()}
                                        </p>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}