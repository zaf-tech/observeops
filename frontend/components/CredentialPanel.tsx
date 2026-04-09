"use client";
import { useState, useRef } from "react";
import { Eye, EyeOff, ChevronDown, ChevronUp, CheckCircle, Circle, Upload, X } from "lucide-react";

export interface PlatformConfig {
  id: string;
  label: string;
  icon: string;
  color: string;
  fields: FieldConfig[];
}

interface FieldConfig {
  key: string;
  label: string;
  placeholder?: string;
  type?: "text" | "password" | "gcpjson";
  required?: boolean;
}

export const PLATFORMS: PlatformConfig[] = [
  {
    id: "aws", label: "Amazon Web Services", icon: "☁️", color: "orange",
    fields: [
      { key: "AWS_ACCESS_KEY_ID",     label: "Access Key ID",       placeholder: "AKIA...",          type: "password", required: true },
      { key: "AWS_SECRET_ACCESS_KEY", label: "Secret Access Key",   placeholder: "••••••••",         type: "password", required: true },
      { key: "AWS_DEFAULT_REGION",    label: "Region",              placeholder: "us-east-1" },
    ],
  },
  {
    id: "azure", label: "Microsoft Azure", icon: "🔷", color: "blue",
    fields: [
      { key: "AZURE_TENANT_ID",       label: "Tenant ID",           placeholder: "xxxxxxxx-...",     type: "password", required: true },
      { key: "AZURE_CLIENT_ID",       label: "Client ID",           placeholder: "xxxxxxxx-...",     type: "password", required: true },
      { key: "AZURE_CLIENT_SECRET",   label: "Client Secret",       placeholder: "••••••••",         type: "password", required: true },
      { key: "AZURE_SUBSCRIPTION_ID", label: "Subscription ID",     placeholder: "xxxxxxxx-...",     type: "password" },
    ],
  },
  {
    id: "gcp", label: "Google Cloud Platform", icon: "🌐", color: "teal",
    fields: [
      { key: "GCP_SERVICE_ACCOUNT_JSON", label: "Service Account Key (JSON file)", type: "gcpjson", required: true },
      { key: "GCP_PROJECT_ID",           label: "Project ID (auto-filled from JSON)", placeholder: "my-project-123" },
    ],
  },
  {
    id: "github", label: "GitHub", icon: "🐙", color: "purple",
    fields: [
      { key: "GITHUB_TOKEN", label: "Personal Access Token", placeholder: "ghp_...", type: "password", required: true },
      { key: "GITHUB_ORG",   label: "Organisation (optional)", placeholder: "my-org" },
    ],
  },
  {
    id: "gitlab", label: "GitLab", icon: "🦊", color: "orange",
    fields: [
      { key: "GITLAB_TOKEN", label: "Personal Access Token", placeholder: "glpat-...", type: "password", required: true },
      { key: "GITLAB_URL",   label: "GitLab URL",            placeholder: "https://gitlab.com" },
      { key: "GITLAB_GROUP", label: "Group (optional)",      placeholder: "my-group" },
    ],
  },
  {
    id: "jenkins", label: "Jenkins", icon: "🏗️", color: "teal",
    fields: [
      { key: "JENKINS_URL",   label: "Jenkins URL",    placeholder: "https://jenkins.example.com", required: true },
      { key: "JENKINS_USER",  label: "Username",       placeholder: "admin",                       required: true },
      { key: "JENKINS_TOKEN", label: "API Token",      placeholder: "••••••••",                    type: "password", required: true },
    ],
  },
  {
    id: "sonarqube", label: "SonarQube / SonarCloud", icon: "📊", color: "blue",
    fields: [
      { key: "SONAR_TOKEN", label: "Token",         placeholder: "squ_...",              type: "password", required: true },
      { key: "SONAR_URL",   label: "URL",           placeholder: "https://sonarcloud.io" },
      { key: "SONAR_ORG",   label: "Organisation",  placeholder: "my-org" },
    ],
  },
  {
    id: "snyk", label: "Snyk", icon: "🛡️", color: "purple",
    fields: [
      { key: "SNYK_TOKEN", label: "API Token", placeholder: "••••••••", type: "password", required: true },
      { key: "SNYK_ORG",   label: "Org ID (optional)", placeholder: "my-org-id" },
    ],
  },
  {
    id: "argocd", label: "ArgoCD", icon: "🚀", color: "teal",
    fields: [
      { key: "ARGOCD_URL",   label: "ArgoCD URL", placeholder: "https://argocd.example.com", required: true },
      { key: "ARGOCD_TOKEN", label: "Auth Token",  placeholder: "••••••••",                   type: "password", required: true },
    ],
  },
  {
    id: "circleci", label: "CircleCI", icon: "⭕", color: "orange",
    fields: [
      { key: "CIRCLECI_TOKEN", label: "Personal API Token", placeholder: "••••••••", type: "password", required: true },
    ],
  },
];

interface Props {
  credentials: Record<string, string>;
  onChange: (key: string, value: string) => void;
}

export default function CredentialPanel({ credentials, onChange }: Props) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set(["aws"]));
  const [showKeys, setShowKeys] = useState<Set<string>>(new Set());
  const [gcpFileName, setGcpFileName] = useState<string | null>(null);

  const toggle = (id: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const toggleShow = (key: string) =>
    setShowKeys((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const handleGcpFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setGcpFileName(file.name);
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      try {
        const parsed = JSON.parse(text);
        onChange("GCP_SERVICE_ACCOUNT_JSON", text);
        // Auto-fill project ID if not already set
        if (parsed.project_id && !credentials["GCP_PROJECT_ID"]) {
          onChange("GCP_PROJECT_ID", parsed.project_id);
        }
      } catch {
        alert("Invalid JSON file — please upload a valid GCP service account key file.");
        setGcpFileName(null);
      }
    };
    reader.readAsText(file);
  };

  const clearGcpJson = () => {
    onChange("GCP_SERVICE_ACCOUNT_JSON", "");
    setGcpFileName(null);
  };

  const isConfigured = (platform: PlatformConfig) =>
    platform.fields.filter((f) => f.required).every((f) => credentials[f.key]?.trim());

  const colorMap: Record<string, string> = {
    orange: "border-orange-500/30 from-orange-500/5",
    blue:   "border-blue-500/30 from-blue-500/5",
    teal:   "border-teal-500/30 from-teal-500/5",
    purple: "border-purple-500/30 from-purple-500/5",
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-300 uppercase tracking-wider">Platform Credentials</h3>
        <span className="text-xs text-gray-500">
          {PLATFORMS.filter(isConfigured).length} / {PLATFORMS.length} configured
        </span>
      </div>

      {PLATFORMS.map((platform) => {
        const isOpen = expanded.has(platform.id);
        const configured = isConfigured(platform);
        const border = colorMap[platform.color] ?? colorMap.teal;

        return (
          <div
            key={platform.id}
            className={`rounded-xl border bg-gradient-to-br ${border} to-transparent transition-all duration-200`}
          >
            {/* Header */}
            <button
              type="button"
              onClick={() => toggle(platform.id)}
              className="w-full flex items-center justify-between px-4 py-3 text-left"
            >
              <div className="flex items-center gap-3">
                <span className="text-lg">{platform.icon}</span>
                <span className="text-sm font-medium text-white">{platform.label}</span>
              </div>
              <div className="flex items-center gap-2">
                {configured
                  ? <CheckCircle className="w-4 h-4 text-teal-400" />
                  : <Circle className="w-4 h-4 text-gray-600" />}
                {isOpen
                  ? <ChevronUp className="w-4 h-4 text-gray-400" />
                  : <ChevronDown className="w-4 h-4 text-gray-400" />}
              </div>
            </button>

            {/* Fields */}
            {isOpen && (
              <div className="px-4 pb-4 space-y-3">
                {platform.fields.map((field) => {
                  const isPassword = field.type === "password";
                  const isGcpJson = field.type === "gcpjson";
                  const visible = showKeys.has(field.key);

                  if (isGcpJson) {
                    const hasFile = Boolean(credentials["GCP_SERVICE_ACCOUNT_JSON"]);
                    return (
                      <div key={field.key}>
                        <label className="block text-xs text-gray-400 mb-1">
                          {field.label}
                          {field.required && <span className="text-teal-400 ml-1">*</span>}
                        </label>
                        {hasFile ? (
                          <div className="flex items-center gap-2 px-3 py-2 bg-teal-500/10 border border-teal-500/30 rounded-lg">
                            <CheckCircle className="w-4 h-4 text-teal-400 flex-shrink-0" />
                            <span className="text-sm text-teal-300 flex-1 truncate">{gcpFileName ?? "service-account.json"}</span>
                            <button
                              type="button"
                              onClick={clearGcpJson}
                              className="text-gray-500 hover:text-red-400 transition-colors"
                              title="Remove"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <label className="flex flex-col items-center justify-center gap-2 px-3 py-4 bg-white/5 border border-dashed border-white/20 rounded-lg cursor-pointer hover:border-teal-500/40 hover:bg-teal-500/5 transition-all group">
                            <Upload className="w-5 h-5 text-gray-500 group-hover:text-teal-400 transition-colors" />
                            <span className="text-xs text-gray-500 group-hover:text-gray-300 transition-colors text-center">
                              Click to upload <strong className="text-gray-400">service account JSON</strong>
                              <br />from Google Cloud Console
                            </span>
                            <input
                              type="file"
                              accept=".json,application/json"
                              className="hidden"
                              onChange={handleGcpFile}
                            />
                          </label>
                        )}
                      </div>
                    );
                  }

                  return (
                    <div key={field.key}>
                      <label className="block text-xs text-gray-400 mb-1">
                        {field.label}
                        {field.required && <span className="text-teal-400 ml-1">*</span>}
                      </label>
                      <div className="relative">
                        <input
                          type={isPassword && !visible ? "password" : "text"}
                          placeholder={field.placeholder}
                          value={credentials[field.key] ?? ""}
                          onChange={(e) => onChange(field.key, e.target.value)}
                          className="w-full px-3 py-2 pr-10 bg-white/5 border border-white/10 rounded-lg text-sm text-white placeholder-gray-600 focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/30 transition-colors"
                          autoComplete="off"
                          spellCheck={false}
                        />
                        {isPassword && (
                          <button
                            type="button"
                            onClick={() => toggleShow(field.key)}
                            className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
                          >
                            {visible ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}

      <p className="text-xs text-gray-600 text-center pt-2">
        🔒 Credentials are held in-memory only — never stored or logged
      </p>
    </div>
  );
}
