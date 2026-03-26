import DocumentHistory from '../components/DocumentHistory';

export default function History() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Історія документів
        </h1>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Всі згенеровані акти та рахунки з можливістю завантаження PDF
        </p>
      </div>

      <DocumentHistory />
    </div>
  );
}
