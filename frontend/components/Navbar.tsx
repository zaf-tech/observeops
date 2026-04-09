"use client";
import Link from "next/link";
import { Shield, Activity, FileText, Cpu } from "lucide-react";

export default function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-teal-500/20 bg-navy/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="relative">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-teal-500 to-electric flex items-center justify-center glow-teal group-hover:scale-110 transition-transform duration-300">
              <Shield className="w-5 h-5 text-white" />
            </div>
            <span className="absolute -top-1 -right-1 w-3 h-3 bg-teal-400 rounded-full animate-pulse" />
          </div>
          <div>
            <span className="text-lg font-bold gradient-text">ObserveOps</span>
            <p className="text-xs text-gray-400 leading-none">by ZafTech</p>
          </div>
        </Link>

        {/* Nav links */}
        <div className="hidden md:flex items-center gap-8">
          <NavLink href="/" icon={<Cpu className="w-4 h-4" />} label="Dashboard" />
          <NavLink href="#status" icon={<Activity className="w-4 h-4" />} label="Scan Status" />
          <NavLink href="#report" icon={<FileText className="w-4 h-4" />} label="Reports" />
        </div>

        {/* CTA */}
        <a
          href="https://zaftech.ca"
          target="_blank"
          rel="noopener noreferrer"
          className="hidden md:inline-flex items-center gap-2 px-4 py-2 bg-cyan-500/10 border border-teal-500/30 rounded-full text-teal-400 text-sm font-medium hover:bg-teal-500/20 transition-colors duration-200"
        >
          <span className="w-2 h-2 bg-teal-400 rounded-full animate-pulse" />
          ZafTech.ca
        </a>
      </div>
    </nav>
  );
}

function NavLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2 text-gray-400 hover:text-teal-400 text-sm transition-colors duration-200"
    >
      {icon}
      {label}
    </Link>
  );
}
