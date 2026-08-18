"use client";

import { useEffect, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { changePassword, getCurrentUser, type AuthUser } from '../../../services/auth';
import { useRequireAuth } from '../../../hooks/useRequireAuth';
import Button from '../../../components/ui/Button';
import Input from '../../../components/ui/Input';
import PageHeader from '../../../components/ui/PageHeader';

export default function ChangePasswordPage() {
  const router = useRouter();
  const { checkingAuth } = useRequireAuth();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [currentPassword, setCurrentPassword] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!checkingAuth) getCurrentUser().then(setUser);
  }, [checkingAuth]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setSuccess('');

    if (!user) return setError('User not loaded yet.');
    if (!currentPassword) return setError('Current password is required.');
    if (password !== confirm) return setError('Passwords do not match.');

    setLoading(true);
    try {
      await changePassword(user.id, password);
      setCurrentPassword('');
      setPassword('');
      setConfirm('');
      setSuccess('Password updated successfully.');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update password');
    } finally {
      setLoading(false);
    }
  }

  if (checkingAuth) return <main className="p-6">Checking session...</main>;

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <PageHeader title="Change Password">
        <Button onClick={() => router.push('/account/profile')}>Back to Profile</Button>
      </PageHeader>

      <form onSubmit={handleSubmit} className="bg-white rounded shadow p-6 max-w-md space-y-4">
        {error && <p className="text-red-600 text-sm">{error}</p>}
        {success && <p className="text-green-600 text-sm">{success}</p>}

        <Input type="password" placeholder="Current password" value={currentPassword} onChange={(e) => setCurrentPassword(e.target.value)} required className="w-full" />
        <Input type="password" placeholder="New password" value={password} onChange={(e) => setPassword(e.target.value)} required className="w-full" />
        <Input type="password" placeholder="Confirm new password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required className="w-full" />

        <Button type="submit" disabled={loading}>
          {loading ? 'Updating...' : 'Update Password'}
        </Button>
      </form>
    </main>
  );
}