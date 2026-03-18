import { ExternalLink } from "lucide-react";

<<<<<<< HEAD
function formatResultDate(value) {
  if (!value) return null;

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function SearchResults({ results = [], query }) {
=======
export default function SearchResults({ results = [], query }) {

>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
  if (!results || results.length === 0) return null;

  return (
    <div className="mb-4 px-4">
<<<<<<< HEAD
=======

>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
      <div className="text-xs text-gray-400 mb-2">
        Web results for "{query}"
      </div>

      <div className="grid gap-2">
<<<<<<< HEAD
        {results.map((item, index) => {
          const formattedDate = formatResultDate(item.date);
          const meta = [formattedDate, item.source].filter(Boolean).join(" | ");

          return (
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

                {meta && (
                  <div className="text-[11px] text-emerald-300 mt-1">
                    {meta}
                  </div>
                )}

                <div className="text-xs text-gray-400 line-clamp-2 mt-1">
                  {item.snippet}
                </div>

                <div className="text-xs text-gray-500 mt-1 truncate">
                  {item.url}
                </div>
              </div>

              <ExternalLink className="w-4 h-4 text-gray-400 ml-2" />
            </a>
          );
        })}
      </div>
    </div>
  );
}
=======

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
>>>>>>> 3520f8c8a820e9822841d33c9bb59a09576e92cf
