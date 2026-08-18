"use client";

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getToken } from '../services/auth';

export function useRequireAuth() {
  const router = useRouter();

  const checkingAuth = typeof window !== 'undefined' && !getToken();

  useEffect(() => {
    if (!getToken()) {
      router.replace('/login');
    }
  }, [router]);

  return { checkingAuth };
}