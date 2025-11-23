import { API_URL } from '../lib/apiConfig';

// API functions for backend settings
export async function apiGetSettings() {
	try {
		const res = await fetch(`${API_URL}/settings`);
		if (!res.ok) throw new Error(`Failed to fetch settings: ${res.status}`);
		return await res.json();
	} catch (error) {
		console.warn('Failed to get settings from backend:', error);
		return { path: '', recurse: true };
	}
}

export async function apiSetSettings(settings: { path: string; recurse: boolean }) {
	try {
		const res = await fetch(`${API_URL}/settings`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(settings)
		});
		if (!res.ok) throw new Error(`Failed to save settings: ${res.status}`);
		return await res.json();
	} catch (error) {
		console.warn('Failed to save settings to backend:', error);
		return settings;
	}
}
