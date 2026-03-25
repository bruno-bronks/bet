import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import Predict from './pages/Predict'
import Models from './pages/Models'

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <main>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/fixtures" element={<Dashboard />} />
          <Route path="/predict" element={<Predict />} />
          <Route path="/historico" element={<History />} />
          <Route path="/models" element={<Models />} />
          <Route path="*" element={
            <div className="flex flex-col items-center justify-center min-h-screen">
              <p className="text-6xl font-black text-slate-800">404</p>
              <p className="text-slate-500 mt-2">Página não encontrada</p>
            </div>
          } />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
