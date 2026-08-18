"use client";

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useRequireAuth } from '../hooks/useRequireAuth';
import { useCandidates } from '../hooks/useCandidates';
import { createCandidate } from '../services/candidates';
import CandidateForm from '../components/candidates/CandidateForm';
import CandidateList from '../components/candidates/CandidateList';
import CandidateFilters from '../components/candidates/CandidateFilters';
import CandidateSearch from '../components/candidates/CandidateSearch';
import Spinner from '../components/ui/Spinner';
import ErrorMessage from '../components/ui/ErrorMessage';
import PageHeader from '../components/ui/PageHeader';

import type { RecordCreate } from '../types/candidate';

export default function HomePage() {
  const { checkingAuth } = useRequireAuth();

  if (checkingAuth) {
    return <div className="p-6">Checking session...</div>;
  }

  return <HomeContent />;
}

function HomeContent() {
  const router = useRouter();
  const searchParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
  const [search, setSearch] = useState(searchParams?.get('search') || '');
  const [status, setStatus] = useState(searchParams?.get('status') || '');
  const [stage, setStage] = useState(searchParams?.get('stage') || '');

  const { candidates, loading, error, refresh } = useCandidates({
    search,
    status,
    stage,
  });

  const updateQuery = (key: string, value: string) => {
    const params = new URLSearchParams(window.location.search);
    if (value) params.set(key, value);
    else params.delete(key);
    router.replace('?' + params.toString());
  };

  const [showForm, setShowForm] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSuccess, setCreateSuccess] = useState(false);

  const handleCreate = async (values: RecordCreate) => {
    setCreateLoading(true);
    setCreateError(null);
    setCreateSuccess(false);

    try {
      await createCandidate(values);
      setCreateSuccess(true);
      setShowForm(false);
      refresh();
    } catch (e) {
      if (e instanceof Error) setCreateError(e.message || 'Failed to create candidate');
      else setCreateError('Failed to create candidate');
    } finally {
      setCreateLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 p-6">
      <PageHeader title="TrackFlow Talent Pipeline">
        <button
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? 'Cancel' : 'Register Candidate'}
        </button>
      </PageHeader>

      {showForm && (
        <div className="mb-6">
          <CandidateForm loading={createLoading} onSubmit={handleCreate} />
          {createError && <ErrorMessage message={createError} />}
          {createSuccess && <div className="text-green-600 text-sm">Candidate registered successfully.</div>}
        </div>
      )}

      <div className="flex flex-col md:flex-row md:items-center md:gap-4 mb-4">
        <div className="flex-1 mb-2 md:mb-0">
          <CandidateSearch
            value={search}
            onChange={(v) => {
              setSearch(v);
              updateQuery('search', v);
            }}
          />
        </div>

        <CandidateFilters
          status={status}
          stage={stage}
          onStatusChange={(v) => {
            setStatus(v);
            updateQuery('status', v);
          }}
          onStageChange={(v) => {
            setStage(v);
            updateQuery('stage', v);
          }}
        />
      </div>

      {loading && <Spinner />}
      {error && <ErrorMessage message={error} />}
      <CandidateList candidates={candidates} />
    </div>
  );
}