export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24 bg-gray-50">
      <div className="text-center">
        <h1 className="text-5xl font-bold text-gray-900 mb-4">
          Привіт, Next.js!
        </h1>
        <p className="text-xl text-gray-600 mb-8">
          Next.js з TypeScript та Tailwind CSS
        </p>
        <div className="flex gap-4 justify-center">
          <a
            href="https://nextjs.org/docs"
            className="px-6 py-3 bg-black text-white rounded-lg hover:bg-gray-800 transition-colors"
            target="_blank"
            rel="noopener noreferrer"
          >
            Документація
          </a>
          <a
            href="https://tailwindcss.com/docs"
            className="px-6 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors"
            target="_blank"
            rel="noopener noreferrer"
          >
            Tailwind CSS
          </a>
        </div>
      </div>
    </main>
  );
}
