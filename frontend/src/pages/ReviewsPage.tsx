function ReviewsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Reviews</h1>
        <p className="text-gray-400 mt-1">Review queue for pending assets</p>
      </div>
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-6">
            <div className="flex items-start gap-4">
              <div className="w-24 h-24 bg-gray-800 rounded-lg flex items-center justify-center">
                <span className="text-gray-600">Preview</span>
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-gray-100">Asset Review #{i}</h3>
                <p className="text-sm text-gray-400 mt-1">Submitted by User {i} • 2 hours ago</p>
                <p className="text-gray-300 mt-2">
                  A character model ready for review. Please check topology and UV mapping.
                </p>
                <div className="flex gap-3 mt-4">
                  <button className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors">
                    Approve
                  </button>
                  <button className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition-colors">
                    Reject
                  </button>
                  <button className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-sm font-medium rounded-lg border border-gray-700 transition-colors">
                    Request Changes
                  </button>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default ReviewsPage;