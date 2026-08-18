"use client";

import { useState } from 'react';
import { useParams } from 'next/navigation';
import { useRequireAuth } from '../../../hooks/useRequireAuth';
import { useCandidate } from '../../../hooks/useCandidate';
import { useNotes } from '../../../hooks/useNotes';
import Spinner from '../../../components/ui/Spinner';
import ErrorMessage from '../../../components/ui/ErrorMessage';
import BackButton from '../../../components/ui/BackButton';
import CandidateDetail from '../../../components/candidates/CandidateDetail';
import CandidateActions from '../../../components/candidates/CandidateActions';
import CandidateEditForm from '../../../components/candidates/CandidateEditForm';
import NotesList from '../../../components/notes/NotesList';
import AddNoteForm from '../../../components/notes/AddNoteForm';

import type { Status, Stage } from '../../../types/candidate';

export default function CandidateDetailPage() {
  const { checkingAuth } = useRequireAuth();

  if (checkingAuth) {
    return <div className="p-6">Checking session...</div>;
  }

  return <CandidateDetailContent />;
}

function CandidateDetailContent() {
  const params = useParams();
  const id = params?.id as string;
  const { candidate, loading, error, refresh, editCandidate, patchStatusStage } = useCandidate(id);
  const { notes, loading: notesLoading, error: notesError, refresh: refreshNotes, createNote, removeNote } = useNotes(id);
  const [editMode, setEditMode] = useState(false);
  const [patchLoading, setPatchLoading] = useState(false);

  const handleStatusChange = async (status: string) => {
    setPatchLoading(true);
    try {
      await patchStatusStage({ status: status as Status });
      refresh();
    } finally {
      setPatchLoading(false);
    }
  };

  const handleStageChange = async (stage: string) => {
    setPatchLoading(true);
    try {
      await patchStatusStage({ stage: stage as Stage });
      refresh();
    } finally {
      setPatchLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <BackButton />
      {loading && <Spinner />}
      {error && <ErrorMessage message={error} />}

      {!loading && candidate && (
        <>
          <CandidateDetail candidate={candidate} />

          <CandidateActions
            status={candidate.status}
            stage={candidate.stage}
            onStatusChange={handleStatusChange}
            onStageChange={handleStageChange}
            loading={patchLoading}
          />

          <button
            className="mb-4 underline text-blue-700"
            onClick={() => setEditMode((v) => !v)}
          >
            {editMode ? 'Cancel Edit' : 'Edit Candidate Info'}
          </button>

          {editMode && (
            <CandidateEditForm
              candidate={candidate}
              loading={patchLoading}
              onSubmit={async (values) => {
                setPatchLoading(true);
                try {
                  await editCandidate(values);
                  refresh();
                  setEditMode(false);
                } finally {
                  setPatchLoading(false);
                }
              }}
            />
          )}

          <h3 className="text-lg font-semibold mt-8 mb-2">Interview Notes</h3>

          <AddNoteForm
            onAdd={async (content) => {
              await createNote({ content });
              refreshNotes();
              refresh();
            }}
            loading={notesLoading}
          />

          {notesError && <ErrorMessage message={notesError} />}

          <NotesList
            notes={notes}
            loading={notesLoading}
            onDelete={async (noteId) => {
              await removeNote(noteId);
              refreshNotes();
              refresh();
            }}
          />
        </>
      )}
    </div>
  );
}