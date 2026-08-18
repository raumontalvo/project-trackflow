"use client";

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { login, register } from '../../services/auth';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError('');

    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);

    try {
      await register(email, password);
      await login(email, password);
      router.push('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-white p-6 rounded shadow space-y-4">
        <h1 className="text-2xl font-bold">Register</h1>

        {error && <p className="text-red-600 text-sm">{error}</p>}

        <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required className="w-full" />
        <Input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required className="w-full" />
        <Input type="password" placeholder="Confirm password" value={confirm} onChange={(e) => setConfirm(e.target.value)} required className="w-full" />

        <Button type="submit" disabled={loading} className="w-full">
          {loading ? 'Creating account...' : 'Register'}
        </Button>

        <button type="button" className="text-blue-700 underline text-sm" onClick={() => router.push('/login')}>
          Already have an account?
        </button>
      </form>
    </main>
  );
}