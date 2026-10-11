import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import RestockOrders from './pages/RestockOrders.jsx'

function NotFound() {
  return (
    <div className="py-16 text-center">
      <p className="text-sm font-medium text-indigo-600">404</p>
      <h1 className="mt-1 text-2xl font-semibold tracking-tight">Page not found</h1>
      <Link to="/" className="mt-4 inline-block text-sm font-medium text-indigo-600 hover:underline">
        Back to the dashboard
      </Link>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="orders" element={<RestockOrders />} />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
