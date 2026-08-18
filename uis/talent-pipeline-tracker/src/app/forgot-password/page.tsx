"use client";

import { useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import { forgotPassword } from '../../services/auth';

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);

    try {
      const response = await forgotPassword(email);
      setMessage(response.message);
      setSubmitted(true);
    } catch {
      setMessage('If that address is in our system, you will receive a password reset link.');
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 p-6">
      <form onSubmit={handleSubmit} className="w-full max-w-sm bg-white p-6 rounded shadow space-y-4">
        <h1 className="text-2xl font-bold">Forgot your password?</h1>

        <p className="text-sm text-gray-600">
          Enter your email address and we will send a reset link if the account exists.
        </p>

        {message && <p className="text-green-700 text-sm">{message}</p>}

        <Input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
          disabled={submitted || loading}
          className="w-full"
        />

        <Button type="submit" disabled={submitted || loading} className="w-full">
          {loading ? 'Sending...' : submitted ? 'Link requested' : 'Send reset link'}
        </Button>

        <button
          type="button"
          className="text-blue-700 underline text-sm"
          onClick={() => router.push('/login')}
        >
          Back to login
        </button>
      </form>
    </main>
  );
}