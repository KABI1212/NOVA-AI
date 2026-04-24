import { ExternalLink } from "lucide-react";

export default function SearchResults({ results = [], query }) {

  if (!results || results.length === 0) return null;

  return (
    <div className="mb-4 px-4">

      <div className="text-xs text-gray-400 mb-2">
        Web results for "{query}"
      </div>

      <div className="grid gap-2">

        {results.map((item, index) => (

          <a
            key={index}
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start justify-between p-3 rounded-lg border border-gray-700 bg-gray-900 hover:bg-gray-800 transition-colors"
          >

            <div className="flex-1 min-w-0">

              <div className="text-sm font-medium text-blue-400 truncate">
                {item.title}
              </div>

              <div className="text-xs text-gray-400 line-clamp-2">
                {item.snippet}
              </div>

              <div className="text-xs text-gray-500 mt-1 truncate">
                {item.url}
              </div>

            </div>

            <ExternalLink className="w-4 h-4 text-gray-400 ml-2"/>

          </a>

        ))}

      </div>

    </div>
  );
}