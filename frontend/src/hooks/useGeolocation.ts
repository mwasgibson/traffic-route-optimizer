import { useState, useCallback } from "react";
import { routeApi } from "@/services/api";
import type { Coordinates } from "@/types";

interface GeolocationState {
  coords: Coordinates | null;
  address: string;
  loading: boolean;
  error: string | null;
  permission: "prompt" | "granted" | "denied" | "unsupported";
}

interface UseGeolocationReturn extends GeolocationState {
  requestLocation: () => void;
  clearError: () => void;
}

export function useGeolocation(): UseGeolocationReturn {
  const [state, setState] = useState<GeolocationState>({
    coords: null,
    address: "",
    loading: false,
    error: null,
    permission: "prompt",
  });

  const requestLocation = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setState((prev) => ({
        ...prev,
        error: "Geolocation is not supported by your browser.",
        permission: "unsupported",
      }));
      return;
    }

    setState((prev) => ({ ...prev, loading: true, error: null }));

    const options: PositionOptions = {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 60000,
    };

    const onSuccess = async (position: GeolocationPosition) => {
      const coords: Coordinates = {
        lat: position.coords.latitude,
        lon: position.coords.longitude,
      };

      // Reverse geocode to get real address
      let address = `My Location (${coords.lat.toFixed(5)}, ${coords.lon.toFixed(5)})`;
      try {
        const result = await routeApi.reverseGeocode(coords.lat, coords.lon);
        if (result.name && result.name !== "Detected Location") {
          address = result.name;
        } else if (result.address && result.address !== "Unknown location") {
          address = result.address;
        }
      } catch {
        // Keep coordinate fallback
      }

      setState({
        coords,
        address,
        loading: false,
        error: null,
        permission: "granted",
      });
    };

    const onError = (error: GeolocationPositionError) => {
      let message = "Unable to retrieve your location.";
      let perm: GeolocationState["permission"] = "denied";

      switch (error.code) {
        case error.PERMISSION_DENIED:
          message =
            'Location access was denied. Please enable location permissions in your browser settings, then click "Use my location" again.';
          perm = "denied";
          break;
        case error.POSITION_UNAVAILABLE:
          message =
            "Location information is unavailable. Please try again or enter your location manually.";
          perm = "prompt";
          break;
        case error.TIMEOUT:
          message =
            "The request to get your location timed out. Please try again.";
          perm = "prompt";
          break;
      }

      setState((prev) => ({
        ...prev,
        loading: false,
        error: message,
        permission: perm,
      }));
    };

    navigator.geolocation.getCurrentPosition(onSuccess, onError, options);
  }, []);

  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  return {
    ...state,
    requestLocation,
    clearError,
  };
}
