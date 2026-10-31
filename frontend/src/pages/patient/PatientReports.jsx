import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../../services/api';
import {
  FileText,
  Calendar,
  Eye,
  X,
  Search,
} from '../../components/common/LucideCompat';
import Button from '../../components/common/Button';
import { Link } from 'react-router-dom';

export default function PatientReports() {
  const [searchQuery, setSearchQuery] = useState('');
  const [previewReport, setPreviewReport] = useState(null);

  // 1. Fetch real reports from the backend
  const { data: realReports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: async () => {
      try {
        const response = await api.get('/reports');
        return response.data;
      } catch (err) {
        console.error("Failed to fetch reports from backend:", err);
        return [];
      }
    },
    retry: 1
  });

  // 2. Present only reports returned by the authenticated backend
  const reportsList = useMemo(() => {
    if (realReports && realReports.length > 0) {
      return realReports.map(r => ({
        id: r.id,
        title: r.title,
        category: r.category.charAt(0).toUpperCase() + r.category.slice(1),
        date: new Date(r.date).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          year: 'numeric'
        }),
        fileType: 'PDF',
        description: r.description,
        therapist: r.therapist,
        content: r.content,
        file_path: r.file_path
      }));
    }
    return [];
  }, [realReports]);

  // 3. Secure download handler
  const handleDownload = async (report) => {
    try {
      const response = await api.get(`/reports/${report.id}/download`, {
        responseType: 'blob'
      });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${report.title.replace(/\s+/g, '_')}_${report.id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to download PDF report:", err);
      alert("Failed to download report. Please try again later.");
    }
  };

  // Search filter
  const filteredReports = useMemo(() => {
    return reportsList.filter((rpt) =>
      rpt.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rpt.category.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [searchQuery, reportsList]);

  return (
    <div className="max-w-[1000px] mx-auto space-y-8 animate-fade-in">
      
      {/* PAGE HEADER */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-[#60716E]">Clinical Records</span>
          <h1 className="text-3xl font-extrabold text-[#183B4A] mt-1">My Reports</h1>
          <p className="mt-2 text-sm sm:text-base text-[#60716E] max-w-2xl leading-relaxed">
            Access clinical assessments and progress summaries compiled by your therapist. Laboratory reports are kept in the laboratory workspace.
          </p>
        </div>
        <Link to="/patient/laboratory" className="inline-flex items-center rounded-xl bg-[#EEF5F1] px-4 py-2 text-sm font-bold text-[#0F6B63]">
          View laboratory reports
        </Link>
      </div>

      {/* SEARCH AND FILTERS */}
      <section className="bg-white border border-[#E5E0D6] rounded-2xl p-4 flex items-center gap-3">
        <Search className="w-5 h-5 text-[#60716E] shrink-0 ml-1" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search reports by title or type (e.g. Assessment)..."
          className="w-full text-sm text-[#183B4A] bg-transparent border-none outline-none placeholder-[#60716E]/70"
        />
      </section>

      {/* REPORTS LIST */}
      <section className="space-y-4">
        {isLoading ? (
          <div className="space-y-3">
            <div className="h-24 bg-gray-100/60 border border-[#E5E0D6]/60 rounded-xl animate-pulse" />
            <div className="h-24 bg-gray-100/60 border border-[#E5E0D6]/60 rounded-xl animate-pulse" />
            <div className="h-24 bg-gray-100/60 border border-[#E5E0D6]/60 rounded-xl animate-pulse" />
          </div>
        ) : filteredReports.length > 0 ? (
          filteredReports.map((rpt) => (
            <div
              key={rpt.id}
              className="bg-white border border-[#E5E0D6] rounded-xl p-5 hover:shadow-[0px_2px_8px_rgba(15,107,99,0.04)] transition flex flex-col sm:flex-row sm:items-center justify-between gap-5"
            >
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-xl bg-[#EEF5F1] flex items-center justify-center border border-[#E5E0D6]/40 shrink-0">
                  <FileText className="w-5 h-5 text-[#0F6B63]" />
                </div>

                <div className="space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-extrabold text-sm sm:text-base text-[#183B4A] leading-snug">
                      {rpt.title}
                    </h3>
                    <span className="px-2 py-0.5 rounded bg-[#DDEFEA] text-[9px] font-extrabold text-[#0F6B63] uppercase border border-[#0F6B63]/10">
                      {rpt.category}
                    </span>
                  </div>
                  
                  <p className="text-xs text-[#60716E] leading-relaxed max-w-xl">
                    {rpt.description}
                  </p>

                  <div className="flex items-center gap-4 text-[10px] font-bold text-[#60716E] pt-1">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5" />
                      {rpt.date}
                    </span>
                    <span>File: {rpt.fileType}</span>
                    <span>ID: {rpt.id}</span>
                  </div>
                </div>
              </div>

              <div className="shrink-0 pt-2 sm:pt-0">
                <button
                  type="button"
                  onClick={() => setPreviewReport(rpt)}
                  className="w-full sm:w-auto flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-bold text-[#0F6B63] hover:text-white bg-[#EEF5F1] hover:bg-[#0F6B63] rounded-xl border border-[#E5E0D6] hover:border-[#0F6B63] transition duration-150"
                >
                  <Eye className="w-4 h-4" />
                  Preview Sample
                </button>
              </div>
            </div>
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-[#E5E0D6] p-12 text-center text-[#60716E]">
            <p className="text-sm">No reports match your search filter criteria.</p>
          </div>
        )}
      </section>

      {/* SAMPLE PREVIEW MODAL */}
      {previewReport && (
        <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs">
          <div className="relative bg-white border border-[#E5E0D6] rounded-2xl max-w-2xl w-full p-6 space-y-6 shadow-xl animate-scale-up">
            
            {/* Modal Header */}
            <div className="flex justify-between items-start gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded bg-[#EEF5F1] text-[9px] font-extrabold text-[#0F6B63] uppercase border border-[#DDEFEA]">
                    {previewReport.category}
                  </span>
                  <span className="text-[10px] font-bold text-[#60716E]">{previewReport.id}</span>
                </div>
                <h2 className="text-lg sm:text-xl font-extrabold text-[#183B4A] mt-2">
                  {previewReport.title}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => setPreviewReport(null)}
                className="w-8 h-8 rounded-lg hover:bg-[#EEF5F1]/50 text-[#60716E] flex items-center justify-center border border-[#E5E0D6]/30 shrink-0"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Document metadata block */}
            <div className="grid grid-cols-2 gap-4 bg-[#F7F4ED]/50 border border-[#E5E0D6]/60 p-4 rounded-xl text-xs text-[#60716E]">
              <div>
                <span className="text-[10px] font-bold text-[#60716E] uppercase block">Assigned Advisor</span>
                <span className="text-sm font-bold text-[#183B4A] mt-0.5 block">{previewReport.therapist}</span>
              </div>
              <div>
                <span className="text-[10px] font-bold text-[#60716E] uppercase block">Record Date</span>
                <span className="text-sm font-bold text-[#183B4A] mt-0.5 block">{previewReport.date}</span>
              </div>
            </div>

            {/* Clinical Content Sections */}
            <div className="space-y-4 text-xs sm:text-sm">
              <div className="space-y-1">
                <h4 className="font-extrabold text-[#183B4A] uppercase tracking-wider text-[10px]">Patient Symptoms</h4>
                <p className="text-[#60716E] leading-relaxed bg-[#F7F4ED]/20 p-2.5 rounded-lg border border-[#E5E0D6]/20">{previewReport.content.symptoms}</p>
              </div>

              <div className="space-y-1">
                <h4 className="font-extrabold text-[#183B4A] uppercase tracking-wider text-[10px]">Clinical Findings</h4>
                <p className="text-[#60716E] leading-relaxed bg-[#F7F4ED]/20 p-2.5 rounded-lg border border-[#E5E0D6]/20">{previewReport.content.findings}</p>
              </div>

              <div className="space-y-1">
                <h4 className="font-extrabold text-[#183B4A] uppercase tracking-wider text-[10px]">Therapist Recommendations</h4>
                <p className="text-[#60716E] leading-relaxed bg-[#F7F4ED]/20 p-2.5 rounded-lg border border-[#E5E0D6]/20">{previewReport.content.recommendations}</p>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="flex justify-end gap-3 pt-2">
              {previewReport.file_path && (
                <Button
                  onClick={() => handleDownload(previewReport)}
                  className="text-xs py-2 px-4 bg-[#0F6B63] hover:bg-[#0F6B63]/90 text-white rounded-xl"
                >
                  Download PDF
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() => setPreviewReport(null)}
                className="text-xs py-2 px-4 border-[#E5E0D6] text-[#60716E] hover:text-[#0F6B63]"
              >
                Close Preview
              </Button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
