"use client";

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { login } from '../../services/auth';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      await login(email, password);
      router.push('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-white p-6 rounded shadow space-y-4">
        <h1 className="text-2xl font-bold">Login</h1>

        {error && <p className="text-red-600 text-sm">{error}</p>}

        <Input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          className="w-full"
        />

        <Input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
          className="w-full"
        />

        <Button type="submit" disabled={loading} className="w-full">
          {loading ? 'Logging in...' : 'Login'}
        </Button>

        <div className="flex items-center justify-between text-sm">
          <button
            type="button"
            className="text-blue-700 underline"
            onClick={() => router.push('/register')}
          >
            Create an account
          </button>

          <button
            type="button"
            className="text-blue-700 underline"
            onClick={() => router.push('/forgot-password')}
          >
            Forgot your password?
          </button>
        </div>
      </form>
    </main>
  );
}