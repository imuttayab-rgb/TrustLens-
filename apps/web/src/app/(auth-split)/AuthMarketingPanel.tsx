import { MapPin, MessageCircle, ScanFace, ShieldCheck } from 'lucide-react';
import Image from 'next/image';

/**
 * The same four features the homepage's "Why choose us" section shows
 * (`Home.features.*`), copied rather than wired through next-intl - this
 * surface (login/register) is English-only today, unlike the marketing
 * site, so pulling in the translation layer for one panel would be its own
 * inconsistency.
 */
const FEATURES = [
  {
    icon: ShieldCheck,
    title: 'Explainable Trust Score',
    body: 'Clear score based on verified data and behaviour.',
  },
  {
    icon: ScanFace,
    title: 'Live identity verification',
    body: 'Sellers verify identity with live ID checks.',
  },
  {
    icon: MessageCircle,
    title: 'Safe in-app chat',
    body: 'Stay protected with secure messaging.',
  },
  {
    icon: MapPin,
    title: 'Platform-curated SafeMeet',
    body: 'Meet in public, verified locations.',
  },
] as const;

export function AuthMarketingPanel() {
  return (
    <div className="relative hidden overflow-hidden bg-muted/30 p-10 lg:flex lg:flex-col lg:justify-center xl:p-16">
      <div className="mx-auto w-full max-w-md">
        <h1 className="text-3xl font-bold tracking-tight xl:text-4xl">
          Join Pakistan&apos;s trusted marketplace
        </h1>
        <p className="mt-3 text-base text-muted-foreground">
          Buy with confidence. Sell with trust.
        </p>

        <div className="relative mx-auto mt-10 aspect-square w-full max-w-sm">
          <Image src="/images/auth-hero.png" alt="" fill priority className="object-contain" />
        </div>

        <div className="mt-10 grid grid-cols-2 gap-6">
          {FEATURES.map((feature) => {
            const Icon = feature.icon;
            return (
              <div key={feature.title} className="flex flex-col items-start gap-2">
                <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand/10 text-brand">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <p className="text-sm font-semibold">{feature.title}</p>
                <p className="text-xs leading-relaxed text-muted-foreground">{feature.body}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
