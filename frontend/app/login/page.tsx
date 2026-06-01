'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { ShieldCheck, User, Key, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

export default function LoginPage() {
    const router = useRouter();
    const [isLoading, setIsLoading] = useState(false);
    const [isFirstTime, setIsFirstTime] = useState(false);
    const [formData, setFormData] = useState({
        username: '',
        password: '',
        confirmPassword: '',
        rememberMe: false,
    });

    // Check if this is first-time setup
    useEffect(() => {
        async function checkFirstTime() {
            try {
                const res = await fetch('/api/auth/check-setup');
                if (res.ok) {
                    const data = await res.json();
                    setIsFirstTime(!data.hasProfile);
                }
            } catch (error) {
                console.error('Failed to check setup status:', error);
            }
        }
        checkFirstTime();
    }, []);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        if (isFirstTime) {
            // First-time registration
            if (formData.password !== formData.confirmPassword) {
                toast.error('Passwords do not match');
                return;
            }
            if (formData.password.length < 8) {
                toast.error('Password must be at least 8 characters');
                return;
            }
        }

        setIsLoading(true);

        try {
            const endpoint = isFirstTime ? '/api/auth/register' : '/api/auth/login';
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username: formData.username,
                    password: formData.password,
                    rememberMe: formData.rememberMe,
                }),
            });

            const data = await res.json();

            if (data.success) {
                toast.success(isFirstTime ? 'Account created successfully!' : 'Welcome back!');
                router.push('/dashboard/home');
            } else {
                toast.error(data.error || 'Authentication failed');
            }
        } catch (error) {
            toast.error('An error occurred. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-zinc-900 dark:via-indigo-950 dark:to-purple-950 p-4">
            <Card className="w-full max-w-md shadow-2xl">
                <CardHeader className="space-y-3 text-center">
                    <div className="mx-auto h-16 w-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg">
                        <ShieldCheck className="h-9 w-9 text-white" />
                    </div>
                    <CardTitle className="text-3xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                        {isFirstTime ? 'Create Your Account' : 'Welcome Back'}
                    </CardTitle>
                    <CardDescription className="text-base">
                        {isFirstTime ? 'Set up your GDPR Agent credentials' : 'Sign in to access your GDPR Agent dashboard'}
                    </CardDescription>
                </CardHeader>

                <form onSubmit={handleSubmit}>
                    <CardContent className="space-y-4">
                        <div className="space-y-2">
                            <Label htmlFor="username" className="flex items-center gap-2">
                                <User className="h-4 w-4" />
                                Username
                            </Label>
                            <Input
                                id="username"
                                type="text"
                                placeholder="Enter your username"
                                value={formData.username}
                                onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                                required
                                disabled={isLoading}
                                className="h-11"
                            />
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="password" className="flex items-center gap-2">
                                <Key className="h-4 w-4" />
                                Password
                            </Label>
                            <Input
                                id="password"
                                type="password"
                                placeholder="Enter your password"
                                value={formData.password}
                                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                required
                                disabled={isLoading}
                                className="h-11"
                            />
                        </div>

                        {isFirstTime && (
                            <div className="space-y-2">
                                <Label htmlFor="confirmPassword" className="flex items-center gap-2">
                                    <Key className="h-4 w-4" />
                                    Confirm Password
                                </Label>
                                <Input
                                    id="confirmPassword"
                                    type="password"
                                    placeholder="Confirm your password"
                                    value={formData.confirmPassword}
                                    onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                                    required
                                    disabled={isLoading}
                                    className="h-11"
                                />
                            </div>
                        )}

                        {!isFirstTime && (
                            <div className="flex items-center space-x-2">
                                <Checkbox
                                    id="remember"
                                    checked={formData.rememberMe}
                                    onCheckedChange={(checked) =>
                                        setFormData({ ...formData, rememberMe: checked as boolean })
                                    }
                                    disabled={isLoading}
                                />
                                <Label htmlFor="remember" className="text-sm cursor-pointer">
                                    Remember me for 30 days
                                </Label>
                            </div>
                        )}
                    </CardContent>

                    <CardFooter className="flex flex-col gap-3">
                        <Button
                            type="submit"
                            className="w-full h-11 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700"
                            disabled={isLoading}
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    {isFirstTime ? 'Creating Account...' : 'Signing In...'}
                                </>
                            ) : (
                                isFirstTime ? 'Create Account' : 'Sign In'
                            )}
                        </Button>

                        <Button
                            type="button"
                            variant="ghost"
                            className="w-full"
                            onClick={() => setIsFirstTime(!isFirstTime)}
                            disabled={isLoading}
                        >
                            {isFirstTime ? 'Already have an account? Sign in' : 'Need an account? Create one'}
                        </Button>
                    </CardFooter>
                </form>
            </Card>
            <div className="absolute bottom-4 text-center text-white/60 text-sm">
                <p>Your data is stored locally and encrypted for privacy</p>
            </div>
        </div>
    );
}
