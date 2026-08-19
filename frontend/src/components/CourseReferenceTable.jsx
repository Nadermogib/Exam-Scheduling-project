import { useState, useEffect } from 'react';
import api from '../api/client';
import '../pages/ResultsPage.css';

export default function CourseReferenceTable() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState('');

  const fetchMappings = async () => {
    try {
      const res = await api.get('/api/reference');
      setRows(res.data.mappings);
    } catch (err) {
      setError('تعذّر تحميل البيانات المرجعية.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMappings();
  }, []);

  const handleEdit = (course_id, dept, currentName) => {
    setEditingId(`${course_id}-${dept}`);
    setEditValue(currentName);
  };

  const handleSave = async (course_id, dept) => {
    if (!editValue.trim()) return;
    try {
      await api.patch(`/api/reference/${course_id}/${encodeURIComponent(dept)}`, {
        display_name: editValue.trim()
      });
      // Update local state to reflect the change
      setRows((prev) => prev.map(r => 
        (r.course_id === course_id && r.department === dept) 
          ? { ...r, display_name: editValue.trim() } 
          : r
      ));
      setEditingId(null);
    } catch (err) {
      alert(err.userMessage || 'تعذّر حفظ التعديل.');
    }
  };

  const handleKeyDown = (e, course_id, dept) => {
    if (e.key === 'Enter') handleSave(course_id, dept);
    if (e.key === 'Escape') setEditingId(null);
  };

  if (loading) return <div style={{ padding: 'var(--space-4)' }}>⏳ جارٍ تحميل البيانات المرجعية...</div>;
  if (error) return <div style={{ padding: 'var(--space-4)', color: 'var(--color-error)' }}>{error}</div>;

  return (
    <div style={{ overflowX: 'auto' }}>
      <table className="reference-table">
        <thead>
          <tr>
            <th>رمز المادة</th>
            <th>القسم</th>
            <th>اسم المقرر</th>
            <th>إجراء</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => {
            const isEditing = editingId === `${r.course_id}-${r.department}`;
            return (
              <tr key={i}>
                <td><code style={{ color: 'var(--color-accent)', fontWeight: 700 }}>{r.course_id}</code></td>
                <td style={{ color: 'var(--color-text-secondary)' }}>{r.department}</td>
                <td>
                  {isEditing ? (
                    <input
                      type="text"
                      className="controls-bar__search"
                      style={{ padding: 'var(--space-1) var(--space-2)' }}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => handleKeyDown(e, r.course_id, r.department)}
                      autoFocus
                    />
                  ) : (
                    r.display_name
                  )}
                </td>
                <td>
                  {isEditing ? (
                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                      <button className="btn btn-primary" style={{ padding: 'var(--space-1) var(--space-2)' }} onClick={() => handleSave(r.course_id, r.department)}>حفظ</button>
                      <button className="btn btn-ghost" style={{ padding: 'var(--space-1) var(--space-2)' }} onClick={() => setEditingId(null)}>إلغاء</button>
                    </div>
                  ) : (
                    <button className="btn btn-secondary" style={{ padding: 'var(--space-1) var(--space-2)' }} onClick={() => handleEdit(r.course_id, r.department, r.display_name)}>
                      ✎ تعديل
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
