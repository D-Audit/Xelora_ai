import { MarketingNav } from '@/components/marketing/nav';
import { MarketingFooter } from '@/components/marketing/footer';
import { HeroSection } from '@/components/marketing/hero-section';
import { ProblemsSection } from '@/components/marketing/problems-section';
import { HowItWorksSection } from '@/components/marketing/how-it-works-section';
import { FeaturesSection } from '@/components/marketing/features-section';
import { ProductPreviewSection } from '@/components/marketing/product-preview-section';
import { AudienceSection } from '@/components/marketing/audience-section';
import { SecuritySection } from '@/components/marketing/security-section';
import { PricingPreviewSection } from '@/components/marketing/pricing-preview-section';
import { FaqSection } from '@/components/marketing/faq-section';
import { CtaSection } from '@/components/marketing/cta-section';
import { TrustSection } from '@/components/marketing/trust-section';

export default function HomePage() {
  return (
    <>
      <MarketingNav />
      <main>
        <HeroSection />
        <TrustSection />
        <ProblemsSection />
        <HowItWorksSection />
        <FeaturesSection />
        <ProductPreviewSection />
        <AudienceSection />
        <SecuritySection />
        <PricingPreviewSection />
        <FaqSection />
        <CtaSection />
      </main>
      <MarketingFooter />
    </>
  );
}
