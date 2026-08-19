"use client";

import { useEffect, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { getCurrentUser, logout, updateProfile, type AuthUser } from '../../../services/auth';
import { useRequireAuth } from '../../../hooks/useRequireAuth';
import Button from '../../../components/ui/Button';
import Input from '../../../components/ui/Input';
import PageHeader from '../../../components/ui/PageHeader';

export default function ProfilePage() {
  const router = useRouter();
  const { checkingAuth } = useRequireAuth();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (checkingAuth) return;

    getCurrentUser()
      .then((currentUser) => {
        setUser(currentUser);
        setName(currentUser.name || '');
        setEmail(currentUser.email);
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load profile'));
  }, [checkingAuth]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!user) return;

    setError('');
    setSuccess('');
    setSaving(true);

    try {
      const updatedUser = await updateProfile(user.id, { name, email });
      setUser(updatedUser);
      setSuccess('Profile updated successfully.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update profile');
    } finally {
      setSaving(false);
    }
  }

  if (checkingAuth) return <main className="p-6">Checking session...</main>;

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <PageHeader title="Account Profile">
        <div className="flex gap-2">
          <Button onClick={() => router.push('/account/change-password')}>Change Password</Button>
          <Button onClick={logout}>Logout</Button>
        </div>
      </PageHeader>

      <form onSubmit={handleSubmit} className="bg-white rounded shadow p-6 max-w-xl space-y-4">
        {error && <p className="text-red-600 text-sm">{error}</p>}
        {success && <p className="text-green-600 text-sm">{success}</p>}

        {user && <p><strong>User ID:</strong> {user.id}</p>}

        <div>
          <label className="block text-sm font-medium mb-1">Name</label>
          <Input value={name} onChange={(event) => setName(event.target.value)} className="w-full" />
        </div>

        <div>
          <label className="block text-sm font-medium mb-1">Email</label>
          <Input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required className="w-full" />
        </div>

        {user && <p><strong>Status:</strong> {user.is_active === false ? 'Inactive' : 'Active'}</p>}

        <Button type="submit" disabled={saving || !user}>
          {saving ? 'Saving...' : 'Save Profile'}
        </Button>
      </form>
    </main>
  );
}