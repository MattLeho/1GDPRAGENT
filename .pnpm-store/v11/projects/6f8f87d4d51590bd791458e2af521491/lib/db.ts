import { Pool, QueryResult } from 'pg';

// Use a global variable to store the connection pool in development
// to prevent exhausting connections during hot reloads.
const globalForDb = global as unknown as { db: Pool };

const pool = globalForDb.db || new Pool({
    connectionString: process.env.DATABASE_URL,
    connectionTimeoutMillis: 5000,
    max: 10,
});

if (process.env.NODE_ENV !== 'production') globalForDb.db = pool;

// Export pool for direct access in API routes
export { pool };

export interface DbQueryResult<T = Record<string, unknown>> {
    rows: T[];
    rowCount: number | null;
    command: string;
    oid: number;
    fields: { name: string; dataTypeID: number }[];
}

/**
 * Database client with proper error handling.
 * No longer returns mock data - errors should be handled by callers.
 */
export const db = {
    /**
     * Execute a SQL query.
     * Throws on connection failure - callers should handle gracefully.
     */
    query: async <T = Record<string, unknown>>(
        text: string,
        params?: (string | number | boolean | null | Date | unknown)[]
    ): Promise<DbQueryResult<T>> => {
        try {
            const result = await pool.query(text, params);
            return result as DbQueryResult<T>;
        } catch (error: unknown) {
            // Log the error but re-throw for caller to handle
            const message = error instanceof Error ? error.message : 'Unknown database error';
            console.error(`Database query failed: ${message}`);
            console.error('Query:', text.substring(0, 200));
            throw error;
        }
    },

    /**
     * Check if the database connection is healthy.
     */
    isHealthy: async (): Promise<boolean> => {
        try {
            await pool.query('SELECT 1');
            return true;
        } catch {
            return false;
        }
    },

    /**
     * Get connection pool stats for debugging.
     */
    getPoolStats: () => ({
        totalCount: pool.totalCount,
        idleCount: pool.idleCount,
        waitingCount: pool.waitingCount,
    }),
};

/**
 * Utility to safely execute a query and return empty array on failure.
 * Use this for non-critical queries where you want graceful degradation.
 */
export async function safeQuery<T = Record<string, unknown>>(
    text: string,
    params?: (string | number | boolean | null | Date | unknown)[]
): Promise<{ rows: T[]; error?: string }> {
    try {
        const result = await db.query<T>(text, params);
        return { rows: result.rows };
    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        return { rows: [], error: message };
    }
}
