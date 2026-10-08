<template>
  <main>
    <slot />
  </main>
</template>

<script setup>
import { LEGAL_ENTITY } from '~/config/legalEntity'

// Global Organization + WebSite JSON-LD structured data
useHead({
  script: [
    {
      type: 'application/ld+json',
      innerHTML: JSON.stringify({
        '@context': 'https://schema.org',
        '@graph': [
          {
            '@type': 'Organization',
            '@id': 'https://projectapp.co/#organization',
            name: 'Project App.',
            legalName: LEGAL_ENTITY.tradeName,
            url: 'https://projectapp.co',
            logo: {
              '@type': 'ImageObject',
              url: 'https://projectapp.co/img/icons/icon-logo-512x512.png',
              width: 512,
              height: 512,
            },
            sameAs: [
              'https://www.instagram.com/projectapp.co/',
              'https://www.facebook.com/projectapp.co',
            ],
            contactPoint: {
              '@type': 'ContactPoint',
              email: LEGAL_ENTITY.email,
              telephone: LEGAL_ENTITY.phone,
              contactType: 'customer service',
              availableLanguage: ['English', 'Spanish'],
            },
            address: {
              '@type': 'PostalAddress',
              streetAddress: LEGAL_ENTITY.address,
              addressLocality: LEGAL_ENTITY.city,
              addressCountry: 'CO',
            },
            description: 'Professional web design and development company specializing in custom software solutions, 3D animations, and e-commerce platforms.',
          },
          {
            '@type': 'WebSite',
            '@id': 'https://projectapp.co/#website',
            url: 'https://projectapp.co',
            name: 'Project App.',
            publisher: { '@id': 'https://projectapp.co/#organization' },
            inLanguage: ['en-US', 'es-CO'],
          },
        ],
      }),
    },
  ],
})
</script>
